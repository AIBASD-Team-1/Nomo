import math

from catalog import TemplateInstance, Vector3
from layout import (
    compute_face_normal,
    generate_layout,
    transform_point,
)


def test_compute_face_normal():
    v1 = (0.0, 0.0, 0.0)
    v2 = (1.0, 0.0, 0.0)
    v3 = (0.0, 1.0, 0.0)
    normal = compute_face_normal(v1, v2, v3)
    assert normal == (0.0, 0.0, 1.0)


def test_transform_point_rotation_and_translation():
    """Acceptance example from Spec.md: Box 100 x 20 x 10 with rotation (90, 0, 90) at (0, 0, 50)."""
    rotation = Vector3(x=90.0, y=0.0, z=90.0)
    position = Vector3(x=0.0, y=0.0, z=50.0)

    # Local corners of box 100 x 20 x 10 centered at bottom face
    local_p1 = (-50.0, -10.0, 0.0)
    local_p2 = (50.0, 10.0, 10.0)

    transformed_p1 = transform_point(local_p1, rotation, position)
    transformed_p2 = transform_point(local_p2, rotation, position)

    # Check that bounding box of transformed points lies within [0, 10], [-50, 50], [40, 60]
    min_x = min(transformed_p1[0], transformed_p2[0])
    max_x = max(transformed_p1[0], transformed_p2[0])
    min_y = min(transformed_p1[1], transformed_p2[1])
    max_y = max(transformed_p1[1], transformed_p2[1])
    min_z = min(transformed_p1[2], transformed_p2[2])
    max_z = max(transformed_p1[2], transformed_p2[2])

    assert math.isclose(min_x, 0.0, abs_tol=1e-5)
    assert math.isclose(max_x, 10.0, abs_tol=1e-5)
    assert math.isclose(min_y, -50.0, abs_tol=1e-5)
    assert math.isclose(max_y, 50.0, abs_tol=1e-5)
    assert math.isclose(min_z, 40.0, abs_tol=1e-5)
    assert math.isclose(max_z, 60.0, abs_tol=1e-5)


def test_box_default_parameters_acceptance_example():
    """Acceptance example from Spec.md: One box with default parameters -> volume 1,000,000 mm3."""
    box_instance = TemplateInstance(
        id="box_1",
        template="box",
        parameters={"length": 100.0, "width": 100.0, "height": 100.0},
        position=Vector3(x=0.0, y=0.0, z=0.0),
        rotation=Vector3(x=0.0, y=0.0, z=0.0),
    )

    layout = generate_layout([box_instance])

    assert len(layout.solids) == 1
    assert math.isclose(layout.total_volume, 1_000_000.0, rel_tol=1e-4)

    bbox = layout.bounding_box
    assert math.isclose(bbox.minimum_x, -50.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_x, 50.0, abs_tol=1e-4)
    assert math.isclose(bbox.minimum_y, -50.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_y, 50.0, abs_tol=1e-4)
    assert math.isclose(bbox.minimum_z, 0.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_z, 100.0, abs_tol=1e-4)
    assert math.isclose(bbox.size_x, 100.0, abs_tol=1e-4)
    assert math.isclose(bbox.size_y, 100.0, abs_tol=1e-4)
    assert math.isclose(bbox.size_z, 100.0, abs_tol=1e-4)


def test_box_with_rotation_acceptance_example():
    """Acceptance example: A box 100 x 20 x 10 with rotation (90, 0, 90) at (0, 0, 50) -> Bounding box x 0..10, y -50..50, z 40..60."""
    box_instance = TemplateInstance(
        id="rotated_box",
        template="box",
        parameters={"length": 100.0, "width": 20.0, "height": 10.0},
        position=Vector3(x=0.0, y=0.0, z=50.0),
        rotation=Vector3(x=90.0, y=0.0, z=90.0),
    )

    layout = generate_layout([box_instance])
    bbox = layout.bounding_box

    assert math.isclose(bbox.minimum_x, 0.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_x, 10.0, abs_tol=1e-4)
    assert math.isclose(bbox.minimum_y, -50.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_y, 50.0, abs_tol=1e-4)
    assert math.isclose(bbox.minimum_z, 40.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_z, 60.0, abs_tol=1e-4)


def test_five_boxes_table_acceptance_example():
    """
    Acceptance example from Spec.md:
    A table of five box instances: top 2000 x 900 x 27 at (0, 0, 723), and legs 70 x 70 x 723 at (+-965, +-415, 0)
    -> A STEP file with 5 solids and a bounding box of 2000 x 900 x 750 mm.
    """
    instances = [
        TemplateInstance(
            id="top",
            template="box",
            parameters={"length": 2000.0, "width": 900.0, "height": 27.0},
            position=Vector3(x=0.0, y=0.0, z=723.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
        TemplateInstance(
            id="leg_1",
            template="box",
            parameters={"length": 70.0, "width": 70.0, "height": 723.0},
            position=Vector3(x=965.0, y=415.0, z=0.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
        TemplateInstance(
            id="leg_2",
            template="box",
            parameters={"length": 70.0, "width": 70.0, "height": 723.0},
            position=Vector3(x=-965.0, y=415.0, z=0.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
        TemplateInstance(
            id="leg_3",
            template="box",
            parameters={"length": 70.0, "width": 70.0, "height": 723.0},
            position=Vector3(x=965.0, y=-415.0, z=0.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
        TemplateInstance(
            id="leg_4",
            template="box",
            parameters={"length": 70.0, "width": 70.0, "height": 723.0},
            position=Vector3(x=-965.0, y=-415.0, z=0.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
    ]

    layout = generate_layout(instances)
    assert len(layout.solids) == 5

    bbox = layout.bounding_box
    assert math.isclose(bbox.minimum_x, -1000.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_x, 1000.0, abs_tol=1e-4)
    assert math.isclose(bbox.minimum_y, -450.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_y, 450.0, abs_tol=1e-4)
    assert math.isclose(bbox.minimum_z, 0.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_z, 750.0, abs_tol=1e-4)

    assert math.isclose(bbox.size_x, 2000.0, abs_tol=1e-4)
    assert math.isclose(bbox.size_y, 900.0, abs_tol=1e-4)
    assert math.isclose(bbox.size_z, 750.0, abs_tol=1e-4)


def test_cylinder_solid_geometry():
    instance = TemplateInstance(
        id="cyl_1",
        template="cylinder",
        parameters={"diameter": 50.0, "height": 100.0},
        position=Vector3(x=0.0, y=0.0, z=0.0),
        rotation=Vector3(x=0.0, y=0.0, z=0.0),
    )
    layout = generate_layout([instance])
    assert len(layout.solids) == 1

    expected_volume = math.pi * (25.0**2) * 100.0
    assert math.isclose(layout.total_volume, expected_volume, rel_tol=1e-3)

    bbox = layout.bounding_box
    assert math.isclose(bbox.minimum_z, 0.0, abs_tol=1e-4)
    assert math.isclose(bbox.maximum_z, 100.0, abs_tol=1e-4)
    assert bbox.size_x <= 50.001
    assert bbox.size_y <= 50.001


def test_sphere_solid_geometry():
    instance = TemplateInstance(
        id="sph_1",
        template="sphere",
        parameters={"diameter": 100.0},
        position=Vector3(x=0.0, y=0.0, z=0.0),
        rotation=Vector3(x=0.0, y=0.0, z=0.0),
    )
    layout = generate_layout([instance])
    assert len(layout.solids) == 1

    expected_volume = (4.0 / 3.0) * math.pi * (50.0**3)
    assert math.isclose(layout.total_volume, expected_volume, rel_tol=1e-3)

    bbox = layout.bounding_box
    # Origin is lowest point of the sphere; centre at height diameter / 2
    assert math.isclose(bbox.minimum_z, 0.0, abs_tol=1e-3)
    assert math.isclose(bbox.maximum_z, 100.0, abs_tol=1e-3)


def test_stl_export():
    box_instance = TemplateInstance(
        id="box_stl",
        template="box",
        parameters={"length": 10.0, "width": 20.0, "height": 30.0},
        position=Vector3(x=0.0, y=0.0, z=0.0),
        rotation=Vector3(x=0.0, y=0.0, z=0.0),
    )
    layout = generate_layout([box_instance])
    stl_output = layout.to_stl("test_box")

    assert stl_output.startswith("solid test_box")
    assert stl_output.strip().endswith("endsolid test_box")
    assert "facet normal" in stl_output
    assert "outer loop" in stl_output
    assert "vertex" in stl_output
    # A box has 12 triangles
    assert stl_output.count("endfacet") == 12


def test_step_export_structure():
    instances = [
        TemplateInstance(
            id="box_part",
            template="box",
            parameters={"length": 50.0, "width": 50.0, "height": 20.0},
            position=Vector3(x=0.0, y=0.0, z=0.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        )
    ]
    layout = generate_layout(instances)
    step_output = layout.to_step("TestModel")

    assert "ISO-10303-21;" in step_output
    assert "HEADER;" in step_output
    assert "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));" in step_output
    assert "DATA;" in step_output
    assert "MANIFOLD_SOLID_BREP('box_part'" in step_output
    assert "CLOSED_SHELL" in step_output
    assert "ADVANCED_FACE" in step_output
    assert "PLANE" in step_output
    assert "POLY_LOOP" in step_output
    assert "CARTESIAN_POINT" in step_output
    assert "ENDSEC;" in step_output
    assert "END-ISO-10303-21;" in step_output
