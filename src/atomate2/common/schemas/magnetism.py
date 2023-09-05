"""Schemas for magnetic ordering calculations."""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field
from pymatgen.analysis.magnetism.analyzer import (
    CollinearMagneticStructureAnalyzer,
    Ordering,
)
from pymatgen.core.structure import Structure


class MagneticOrderingInput(BaseModel):
    """Defines the input structure/ordering for a magnetic ordering calculation.

    This is embedded in the MagneticOrderingOutput and MagneticOrderingRelaxation
    documents.
    """

    structure: Structure = Field(None, description="Input structure")
    ordering: Ordering = Field(
        None,
        description=(
            "The magnetic ordering of the input structure, "
            "as defined in pymatgen.analysis.magnetism.analyzer."
        ),
    )
    magmoms: list[float] = Field(None, description="Magnetic moments of the structure.")
    symmetry: str = Field(None, description="Detected space group symbol.")


class MagneticOrderingRelaxation(BaseModel):
    """Defines the relaxation information for a magnetic ordering calculation.

    This is embedded within the MagneticOrderingOutput.
    """

    uuid: str = Field(None, description="Unique ID of the calculation.")
    dir_name: str = Field(None, description="Directory of the calculation.")
    input: MagneticOrderingInput = Field(
        None, description="Input ordering information."
    )
    structure: Structure = Field(
        None, description="Final structure from the calculation."
    )
    symmetry_changed: bool = Field(None, description="Whether or not symmetry changed.")
    ordering_changed: bool = Field(
        None,
        description=(
            "Specifies whether or not the magnetic ordering changed during the"
            " calculation."
        ),
    )
    ordering: Ordering = Field(None, description="Final ordering from the calculation.")
    magmoms: list[float] = Field(None, description="Magnetic moments of the structure.")
    symmetry: str = Field(None, description="Detected space group symbol.")
    energy: float = Field(None, description="Final energy result from the calculation.")
    energy_per_atom: float = Field(None, description="Final energy per atom.")
    total_magnetization: float = Field(
        None,
        description=(
            "Total magnetization as a sum of individual atomic moments in "
            "the calculated unit cell."
        ),
    )
    total_magnetization_per_formula_unit: float = Field(
        None, description="Total magnetization normalized to per formula unit."
    )
    total_magnetization_per_unit_volume: float = Field(
        None, description="Total magnetiation noramlized to per unit volume."
    )

    @classmethod
    def from_structures_and_energies(
        cls,
        input_structure,
        output_structure,
        output_energy,
        uuid: str | None = None,
        dir_name: str | None = None,
    ) -> MagneticOrderingRelaxation:
        """Construct a relaxation output doc from structures and energies."""
        return cls(
            uuid=uuid,
            dir_name=dir_name,
            structure=output_structure,
            energy=output_energy,
            energy_per_atom=output_energy / output_structure.num_sites,
            **_compare_ordering_and_symmetry(input_structure, output_structure),
        )

    @classmethod
    def from_task_document(
        cls, task_document, uuid: str | None = None
    ) -> MagneticOrderingRelaxation:
        """Construct a MagneticOrderingRelaxation output doc from a task document.

        This is to be implemented for the DFT code of choice.
        """
        raise NotImplementedError


class MagneticOrderingOutput(BaseModel):
    """Defines the output for a *static* magnetic ordering calculation.

    This is used within the construction of the MagneticOrderingDocument. If a
    relaxation was performed, this information will be stored within the
    relax_output field.
    """

    uuid: str = Field(None, description="Unique ID of the calculation.")
    dir_name: str = Field(None, description="Directory of the calculation.")
    input: MagneticOrderingInput = Field(
        None, description="Input ordering information."
    )
    structure: Structure = Field(
        None, description="Final structure from the calculation."
    )
    ordering: Ordering = Field(
        None,
        description=(
            "The magnetic ordering of the output structure, "
            "as defined in pymatgen.analysis.magnetism.analyzer."
        ),
    )
    magmoms: list[float] = Field(None, description="Magnetic moments of the structure.")
    symmetry: str = Field(None, description="Detected space group symbol.")
    energy: float = Field(None, description="Final energy result from the calculation.")
    energy_per_atom: float = Field(None, description="Final energy per atom.")
    total_magnetization: float = Field(
        None,
        description=(
            "Total magnetization as a sum of individual atomic moments in "
            "the calculated unit cell."
        ),
    )
    total_magnetization_per_formula_unit: float = Field(
        None, description="Total magnetization normalized to per formula unit."
    )
    total_magnetization_per_unit_volume: float = Field(
        None, description="Total magnetiation noramlized to per unit volume."
    )
    ordering_changed: bool = Field(
        None,
        description=(
            "Specifies whether or not the magnetic ordering changed during the"
            " calculation."
        ),
    )
    symmetry_changed: bool = Field(
        None,
        description=(
            "Specifies whether or not the symmetry changed during the calculation."
        ),
    )
    energy_above_ground_state_per_atom: float = Field(
        None, description="Energy per atom above the calculated ground state ordering."
    )
    relax_output: MagneticOrderingRelaxation | None = Field(
        None, description="Relaxation output, if relaxation performed."
    )
    energy_diff_relax_static: str | float | None = Field(
        None,
        description=(
            "Difference in energy between relaxation and final static calculation, if"
            " relaxation performed (useful for benchmarking). Specifically, this is"
            " calculated as energy[static] - energy[relax]."
        ),
    )

    @classmethod
    def from_structures_and_energies(
        cls,
        input_structure: Structure,
        output_structure: Structure,
        output_energy: float,
        relax_output: MagneticOrderingRelaxation | None = None,
        uuid: str | None = None,
        dir_name: str | None = None,
        ground_state_energy_per_atom: float | None = None,
    ) -> MagneticOrderingOutput:
        """Construct a MagneticOrderingOutput doc from structures and energies."""
        energy_diff_relax_static = (
            relax_output.energy - output_energy if relax_output else None
        )
        output_energy_per_atom = output_energy / output_structure.num_sites
        energy_above_ground_state_per_atom = (
            output_energy_per_atom - ground_state_energy_per_atom
            if ground_state_energy_per_atom
            else None
        )
        return cls(
            uuid=uuid,
            dir_name=dir_name,
            structure=output_structure,
            energy=output_energy,
            relax_output=relax_output,
            energy_diff_relax_static=energy_diff_relax_static,
            energy_per_atom=output_energy_per_atom,
            energy_above_ground_state_per_atom=energy_above_ground_state_per_atom,
            **_compare_ordering_and_symmetry(input_structure, output_structure),
        )

    @classmethod
    def from_task_document(
        cls, task_document, uuid: str | None = None
    ) -> MagneticOrderingOutput:
        """Construct a MagnetismOutput from a task document.

        This is to be implemented for the DFT code of choice.
        """
        raise NotImplementedError


class MagneticOrderingsDocument(BaseModel):
    """Final document containing information about calculated magnetic orderings.

    Includes description of the ground state ordering. This document is returned by the
    MagneticOrderingsBuilder corresponding to your DFT code.
    """

    formula: str = Field(
        None,
        description="Formula taken from pymatgen.core.structure.Structure.formula.",
    )
    formula_pretty: str = Field(
        None,
        description="Cleaned representation of the formula",
    )
    parent_structure: Structure = Field(
        None,
        description=(
            "The parent structure from which individual magnetic "
            "orderings are generated."
        ),
    )
    outputs: list[MagneticOrderingOutput] = Field(
        None,
        description="All magnetic ordering calculation results for this structure.",
    )
    ground_state_uuid: str = Field(
        None, description="UUID of the ground state ordering."
    )
    ground_state_structure: Structure = Field(
        None, description="Ground state structure."
    )
    ground_state_ordering: Ordering = Field(None, description="Ground state ordering.")
    ground_state_energy: float = Field(None, description="Ground state energy.")
    ground_state_energy_per_atom: float = Field(
        None, description="Ground state energy."
    )

    @classmethod
    def from_outputs(
        cls,
        outputs: list[MagneticOrderingOutput],
        parent_structure: Structure,
    ) -> MagneticOrderingsDocument:
        """Construct a MagneticOrderingDocument from a list of output docs.

        This is general and should not need to be implemented for a specific DFT code.
        """
        formula = outputs[0].structure.formula
        formula_pretty = outputs[0].structure.composition.reduced_formula

        ground_state = min(outputs, key=lambda struct: struct.energy_per_atom)
        ground_state_energy_per_atom = ground_state.energy_per_atom
        for output in outputs:
            output.energy_above_ground_state_per_atom = (
                output.energy_per_atom - ground_state_energy_per_atom
            )

        return cls(
            formula=formula,
            formula_pretty=formula_pretty,
            parent_structure=parent_structure,
            outputs=outputs,
            ground_state_uuid=ground_state.uuid,
            ground_state_structure=ground_state.structure,
            ground_state_ordering=ground_state.ordering,
            ground_state_energy=ground_state.energy,
            ground_state_energy_per_atom=ground_state.energy_per_atom,
        )

    @classmethod
    def from_tasks(cls, tasks: list[dict]):
        """Construct a MagneticOrderingsDocument from a list of task dicts.

        This uses the _build_relax_output and _build_static_output methods to construct
        the MagneticOrderingRelaxation and MagneticOrderingOutput docs, respectively.
        These methods need to be implemented for the DFT code of choice.

        Note: this function assumes the tasks contain the keys "output" and "metadata".
        These keys are automatically constructed when jobflow stores its outputs;
        however, you may need to put the data in this format if using this manually (as
        in a postprocessing job).

        """
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
                    relax_output = cls._build_relax_output(
                        r_task["output"],
                        uuid=r_task["uuid"],
                    )
                    break
            output = cls._build_static_output(
                task["output"],
                uuid=task["uuid"],
                relax_output=relax_output,
            )
            outputs.append(output)

        return cls.from_outputs(outputs, parent_structure=parent_structure)

    @staticmethod
    def _build_relax_output(relax_task, uuid=None) -> MagneticOrderingRelaxation:
        """Wrap the function MagneticOrderingRelaxation.from_task_document."""
        raise NotImplementedError

    @staticmethod
    def _build_static_output(
        static_task, uuid=None, relax_output=None
    ) -> MagneticOrderingOutput:
        """Warp the function MagneticOrderingOutput.from_task_document."""
        raise NotImplementedError


def _compare_ordering_and_symmetry(
    input_structure: Structure, output_structure: Structure
) -> dict:
    """Compare ordering and symmetry of input and output structures.

    This is especially useful for debugging purposes.
    """
    # process input structure
    input_analyzer = CollinearMagneticStructureAnalyzer(input_structure, threshold=0.61)
    input_ordering = input_analyzer.ordering
    input_magmoms = input_analyzer.magmoms
    input_symmetry = input_structure.get_space_group_info()[0]

    # process output structure
    output_analyzer = CollinearMagneticStructureAnalyzer(
        output_structure, threshold=0.61
    )
    output_ordering = output_analyzer.ordering
    output_magmoms = output_analyzer.magmoms
    output_symmetry = output_structure.get_space_group_info()[0]
    total_magnetization = output_analyzer.total_magmoms
    num_formula_units = (
        output_structure.composition.get_reduced_composition_and_factor()[1]
    )
    total_magnetization_per_formula_unit = total_magnetization / num_formula_units
    total_magnetization_per_unit_volume = total_magnetization / output_structure.volume

    # compare
    ordering_changed = not np.array_equal(
        np.sign(input_analyzer.magmoms), np.sign(output_magmoms)
    )
    symmetry_changed = output_symmetry != input_symmetry

    input = MagneticOrderingInput(
        structure=input_structure,
        ordering=input_ordering,
        magmoms=list(input_magmoms),
        symmetry=input_symmetry,
    )

    return {
        "input": input,
        "magmoms": list(output_magmoms),
        "ordering": output_ordering,
        "symmetry": output_symmetry,
        "ordering_changed": ordering_changed,
        "symmetry_changed": symmetry_changed,
        "total_magnetization": total_magnetization,
        "total_magnetization_per_formula_unit": total_magnetization_per_formula_unit,
        "total_magnetization_per_unit_volume": total_magnetization_per_unit_volume,
    }
