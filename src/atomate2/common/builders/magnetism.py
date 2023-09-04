"""Module defining DFT code agnostic magnetic orderings builder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from emmet.core.utils import jsanitize
from maggma.builders import Builder
from monty.serialization import MontyDecoder

from atomate2.common.schemas.magnetism import MagneticOrderingsDocument

if TYPE_CHECKING:
    from maggma.core import Store

    from atomate2.common.schemas.magnetism import (
        MagneticOrderingOutput,
        MagneticOrderingRelaxation,
    )


class MagneticOrderingsBuilder(Builder):
    """Builder to analyze the results of magnetic orderings calculations.

    This job will process the output documents of the calculations and return new
    documents with relevant parameters (such as the total magnetization, whether the
    ordering changed, whether the particular ordering is the ground state, etc.).

    .. Note::
        This builder can be trivially implemented for your DFT code of choice by
        adding functionality for constructing the static/relax outputs (see schema for
        details) and implementing the 1) _build_relax_output, 2) _build_static_output,
        and 3) _dft_code_query methods.

    Parameters
    ----------
    tasks : .Store
        Store of task documents.
    magnetic_orderings : .Store
        Store for magnetic ordering documents.
    query : dict
        Dictionary query to limit tasks to be analyzed.
    structure_match_tol : float
        Numerical tolerance for structure equivalence.
    **kwargs
        Keyword arguments that will be passed to the Builder init.
    """

    def __init__(
        self,
        tasks: Store,
        magnetic_orderings: Store,
        query: dict = None,
        structure_match_tol: float = 1e-5,
        **kwargs,
    ):
        self.tasks = tasks
        self.magnetic_orderings = magnetic_orderings
        self.query = query if query else {}
        self.structure_match_tol = structure_match_tol
        self.kwargs = kwargs

        super().__init__(sources=[tasks], targets=[magnetic_orderings], **kwargs)

    def ensure_indexes(self):
        """Ensure indices on the tasks and magnetic orderings collections."""
        self.tasks.ensure_index("output.formula_pretty")
        self.tasks.ensure_index("last_updated")
        self.magnetic_orderings.ensure_index("last_updated")

    def get_items(self):
        """Get all items to process into magnetic ordering documents.

        This step does a first grouping by formula (which is fast) and then the magnetic
        orderings are grouped by parent structure.

        Yields
        ------
        list of dict
            A list of magnetic ordering relaxation or static task outputs, grouped by
            formula.
        """
        self.logger.info("Magnetic orderings builder started")
        self.logger.debug("Adding/ensuring indices...")
        self.ensure_indexes()

        criteria = dict(self.query)
        criteria.update(self._dft_code_query)
        criteria.update(
            {
                "metadata.ordering": {"$exists": True},
            }
        )
        self.logger.info("Grouping by formula...")
        num_formulas = len(
            self.tasks.distinct("output.formula_pretty", criteria=criteria)
        )
        results = self.tasks.groupby("output.formula_pretty", criteria=criteria)
        self.logger.info("Aggregation complete")

        for n_formula, (keys, docs) in enumerate(results):
            formula = keys["output"]["formula_pretty"]
            self.logger.debug(
                f"Getting {formula} (Formula {n_formula + 1} of {num_formulas})"
            )
            decoded_docs = MontyDecoder().process_decoded(docs)
            grouped_tasks = _group_orderings(decoded_docs, self.structure_match_tol)
            n_groups = len(grouped_tasks)
            for n_group, group in enumerate(grouped_tasks):
                self.logger.debug(
                    f"Found {len(group)} tasks for {formula} (Parent structure"
                    f" {n_group+1} of {n_groups})"
                )
                yield group

    def process_item(self, tasks: list[dict]) -> list[MagneticOrderingsDocument]:
        """Process magnetic ordering relaxation/static calculations into documents.

        The magnetic ordering tasks will be grouped based on their parent structure
        (i.e., the structure before the magnetic ordering transformation was applied).

        Parameters
        ----------
        tasks : list of dict
            A list of magnetic ordering tasks grouped by same formula.

        Returns
        -------
        list of .MagneticOrderingsDocument
            A list of magnetic ordering documents (one for each unique parent
            structure).
        """
        self.logger.debug(f"Processing {tasks[0]['output'].formula_pretty}")

        if not tasks:
            return []

        parent_structure = tasks[0]["metadata"]["parent_structure"]

        relax_tasks, static_tasks = [], []
        for task in tasks:
            if task["output"].task_type.value.lower() == "structure optimization":
                relax_tasks.append(task)
            elif task["output"].task_type.value.lower() == "static":
                static_tasks.append(task)

        outputs = []
        for task in static_tasks:
            relax_output = None
            for r_task in relax_tasks:
                if r_task["uuid"] == task["metadata"]["parent_uuid"]:
                    relax_output = self._build_relax_output(
                        r_task["output"],
                        uuid=r_task["uuid"],
                    )
                    break
            output = self._build_static_output(
                task["output"],
                uuid=task["uuid"],
                relax_output=relax_output,
            )
            outputs.append(output)

        return jsanitize(
            MagneticOrderingsDocument.from_outputs(
                outputs, parent_structure=parent_structure
            ).dict(),
            allow_bson=True,
        )

    def update_targets(self, items: list[MagneticOrderingsDocument]):
        """Insert new magnetic orderings into the magnetic orderings Store.

        Parameters
        ----------
        items : list of .MagneticOrderingsDocument
            A list of magnetic ordering documents to add to the database.
        """
        self.logger.info(f"Updating {len(items)} magnetic orderings documents")
        self.magnetic_orderings.update(items, key="ground_state_uuid")

    def _build_relax_output(self, relax_task, uuid=None) -> MagneticOrderingRelaxation:
        """Wrap the function MagneticOrderingRelaxation.from_task_document."""
        raise NotImplementedError

    def _build_static_output(
        self, static_task, uuid=None, relax_output=None
    ) -> MagneticOrderingOutput:
        """Warp the function MagneticOrderingOutput.from_task_document."""
        raise NotImplementedError

    @property
    def _dft_code_query(self):
        """Return a query criterion for querying the tasks collection for tasks.

        This is to be implemented for the DFT code of choice. This prevents mixing of
        tasks from different DFT codes in the same builder.
        """
        raise NotImplementedError


def _group_orderings(tasks: list[dict], tol: float) -> list[list[dict]]:
    """Group deformation tasks by their parent structure.

    Parameters
    ----------
    tasks : list of dict
        A list of deformation tasks.
    tol : float
        Numerical tolerance for structure equivalence.

    Returns
    -------
    list of list of dict
        The tasks grouped by their parent (undeformed structure).
    """
    grouped_tasks = [[tasks[0]]]

    for task in tasks[1:]:
        parent_structure = task["metadata"]["parent_structure"]

        match = False
        for group in grouped_tasks:
            group_parent_structure = task["metadata"]["parent_structure"]

            # parent structure should really be exactly identical (from same workflow)
            lattice_match = np.allclose(
                parent_structure.lattice.matrix,
                group_parent_structure.lattice.matrix,
                atol=tol,
            )
            coords_match = np.allclose(
                parent_structure.frac_coords,
                group_parent_structure.frac_coords,
                atol=tol,
            )
            if lattice_match and coords_match:
                group.append(task)
                match = True
                break

        if not match:
            grouped_tasks.append([task])

    return grouped_tasks
