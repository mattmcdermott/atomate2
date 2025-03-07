def test_sort_pos_dist():
    """
    Test the sorting algorithm with a list of 2D positions.
    The algorithm should sort the list into a straight line depending on the direction
    of s1 and s2
    """
    import numpy as np

    from atomate2.common.analysis.defects.schemas import sort_pos_dist

    def abs_d(s1, s2):
        return np.linalg.norm(np.array(s1) - np.array(s2))

    points_on_line_2d = [(1, 1), (-2, -2), (0, 0), (2, 2), (-1, -1)]
    r, d = sort_pos_dist(points_on_line_2d, s1=(0, 0), s2=(1.5, 1.5), dist=abs_d)
    assert r == [(-2, -2), (-1, -1), (0, 0), (1, 1), (2, 2)]

    r, d = sort_pos_dist(points_on_line_2d, s1=(0, 0), s2=(-2.5, -2.5), dist=abs_d)
    assert r == [(2, 2), (1, 1), (0, 0), (-1, -1), (-2, -2)]


def test_CCDDocument(vasp_test_dir):
    """
    Test the CCDDocument schema
    """
    from collections import defaultdict

    from atomate2.common.analysis.defects.schemas import CCDDocument
    from atomate2.vasp.schemas.task import TaskDocument

    def is_strict_minimum(min_index, arr):
        min_val = arr[min_index]
        return all(not (i != min_index and val < min_val) for i, val in enumerate(arr))

    static_tasks1: list[TaskDocument] = []
    static_tasks2: list[TaskDocument] = []
    static_dirs1: list[str] = []
    static_dirs2: list[str] = []
    for i in range(5):
        sdir1 = vasp_test_dir / "Si_config_coord" / f"static_q1_{i}" / "outputs"
        sdir2 = vasp_test_dir / "Si_config_coord" / f"static_q2_{i}" / "outputs"
        static_tasks1.append(TaskDocument.from_directory(sdir1))
        static_tasks2.append(TaskDocument.from_directory(sdir2))
        static_dirs1.append(str(sdir1))
        static_dirs2.append(str(sdir2))

    inputs1 = [
        (task.output.structure, task.output.energy, sdir)
        for task, sdir in zip(static_tasks1, static_dirs1)
    ]
    inputs2 = [
        (task.output.structure, task.output.energy, sdir)
        for task, sdir in zip(static_tasks2, static_dirs2)
    ]

    inputdict = defaultdict(list)

    for s, e, sdir in inputs1:
        inputdict["structures1"].append(s)
        inputdict["energies1"].append(e)
        inputdict["static_dirs1"].append(sdir)
        inputdict["static_uuids1"].append(sdir)

    for s, e, sdir in inputs2:
        inputdict["structures2"].append(s)
        inputdict["energies2"].append(e)
        inputdict["static_dirs2"].append(sdir)
        inputdict["static_uuids2"].append(sdir)

    inputdict["relaxed_uuid1"] = static_dirs1[2]
    inputdict["relaxed_uuid2"] = static_dirs2[2]

    ccd_doc = CCDDocument.from_task_outputs(
        **inputdict,
    )

    # create the CCD document
    # ccd_doc = CCDDocument.from_struct_en(static_tasks1, static_tasks2, s0, s1)
    # # check that the middle entry has the lowest energy
    assert is_strict_minimum(2, ccd_doc.energies1)
    assert is_strict_minimum(2, ccd_doc.energies2)
    # # check that you can recreate the task document from the ccd document
    tasks = ccd_doc.get_taskdocs()
    assert len(tasks[0]) == 5
    assert len(tasks[1]) == 5
