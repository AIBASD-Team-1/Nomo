"""Deep validation tests for generated STL and STEP CAD files."""

import math
import re
from pathlib import Path

from catalog import TemplateInstance, Vector3
from layout import generate_layout


def parse_ascii_stl(stl_content: str) -> dict:
    """
    Parse ASCII STL content and validate strict STL grammar:

    solid <name>
      facet normal <nx> <ny> <nz>
        outer loop
          vertex <x> <y> <z>
          vertex <x> <y> <z>
          vertex <x> <y> <z>
        endloop
      endfacet
      ...
    endsolid <name>
    """
    lines = [line.strip() for line in stl_content.strip().splitlines() if line.strip()]
    assert len(lines) >= 2, "STL file too short"
    assert lines[0].startswith("solid "), "STL must begin with 'solid <name>'"
    solid_header_name = lines[0].split(maxsplit=1)[1]
    assert lines[-1].startswith("endsolid"), "STL must end with 'endsolid'"

    facets = []
    current_normal = None
    current_vertices: list[tuple[float, float, float]] = []
    in_facet = False
    in_loop = False

    normal_regex = re.compile(
        r"^facet\s+normal\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)$"
    )
    vertex_regex = re.compile(
        r"^vertex\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)$"
    )

    for line in lines[1:-1]:
        if line.startswith("facet normal"):
            assert not in_facet, "Nested facet detected"
            match = normal_regex.match(line)
            assert match is not None, f"Malformed facet normal: {line}"
            current_normal = (
                float(match.group(1)),
                float(match.group(2)),
                float(match.group(3)),
            )
            in_facet = True
            current_vertices = []
        elif line == "outer loop":
            assert in_facet, "outer loop outside of facet"
            assert not in_loop, "nested loop detected"
            in_loop = True
        elif line.startswith("vertex"):
            assert in_loop, "vertex outside of loop"
            match = vertex_regex.match(line)
            assert match is not None, f"Malformed vertex: {line}"
            current_vertices.append(
                (
                    float(match.group(1)),
                    float(match.group(2)),
                    float(match.group(3)),
                )
            )
        elif line == "endloop":
            assert in_loop, "endloop without outer loop"
            assert len(current_vertices) == 3, (
                f"Facet must have exactly 3 vertices, got {len(current_vertices)}"
            )
            in_loop = False
        elif line == "endfacet":
            assert in_facet, "endfacet without facet normal"
            assert not in_loop, "endfacet before endloop"
            facets.append(
                {
                    "normal": current_normal,
                    "vertices": current_vertices,
                }
            )
            in_facet = False

    return {
        "solid_name": solid_header_name,
        "facets": facets,
    }


def parse_step_file(step_content: str) -> dict:
    """
    Parse an ISO 10303-21 STEP file and validate syntax and referential integrity:

    - Verifies ISO-10303-21 header and trailer tokens.
    - Verifies HEADER and DATA sections.
    - Extracts all entity definitions #ID = TYPE(...);
    - Validates that every referenced #ID exists within the file (no dangling pointers).
    """
    assert "ISO-10303-21;" in step_content, "Missing ISO-10303-21 start token"
    assert "END-ISO-10303-21;" in step_content, "Missing END-ISO-10303-21 end token"
    assert "HEADER;" in step_content, "Missing HEADER section"
    assert "DATA;" in step_content, "Missing DATA section"

    # Extract DATA section
    data_start = step_content.find("DATA;")
    data_end = step_content.find("ENDSEC;", data_start)
    assert data_start != -1 and data_end != -1, (
        "DATA section must be terminated with ENDSEC;"
    )
    data_section = step_content[data_start + len("DATA;") : data_end]

    # Parse entities: #ID = ...;
    entity_pattern = re.compile(r"^#(\d+)\s*=\s*(.+?);\s*$", re.MULTILINE)
    reference_pattern = re.compile(r"#(\d+)")

    entities: dict[int, dict] = {}
    all_referenced_ids: set[int] = set()

    for match in entity_pattern.finditer(data_section):
        entity_id = int(match.group(1))
        entity_body = match.group(2).strip()

        # Extract type for simple entities: TYPE(...)
        type_match = re.match(r"^([A-Za-z0-9_]+)\s*\(", entity_body)
        entity_type = type_match.group(1) if type_match else "COMPLEX_ENTITY"

        assert entity_id not in entities, f"Duplicate entity ID detected: #{entity_id}"
        entities[entity_id] = {
            "type": entity_type,
            "raw_body": entity_body,
        }

        # Collect references to other entities
        for ref_match in reference_pattern.finditer(entity_body):
            all_referenced_ids.add(int(ref_match.group(1)))

    return {
        "entities": entities,
        "referenced_ids": all_referenced_ids,
    }


def test_stl_file_exact_structure_and_normals():
    """Verify that generated STL has exact valid geometry, correct normals and CCW winding."""
    box_instance = TemplateInstance(
        id="unit_box",
        template="box",
        parameters={"length": 100.0, "width": 100.0, "height": 100.0},
        position=Vector3(x=0.0, y=0.0, z=0.0),
        rotation=Vector3(x=0.0, y=0.0, z=0.0),
    )
    layout = generate_layout([box_instance])
    stl_text = layout.to_stl("test_unit_box")

    parsed_stl = parse_ascii_stl(stl_text)
    assert parsed_stl["solid_name"] == "test_unit_box"

    facets = parsed_stl["facets"]
    assert len(facets) == 12, "Box must have exactly 12 triangular facets (2 per face)"

    # Verify each facet: normal is non-zero, vertices are distinct, normal matches cross product
    for facet in facets:
        normal = facet["normal"]
        normal_magnitude = math.sqrt(sum(component**2 for component in normal))
        assert math.isclose(normal_magnitude, 1.0, rel_tol=1e-4), (
            "Normal must be normalized unit vector"
        )

        v1, v2, v3 = facet["vertices"]
        # Vertices must not be degenerate
        edge_1 = (v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2])
        edge_2 = (v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2])
        cross_product = (
            edge_1[1] * edge_2[2] - edge_1[2] * edge_2[1],
            edge_1[2] * edge_2[0] - edge_1[0] * edge_2[2],
            edge_1[0] * edge_2[1] - edge_1[1] * edge_2[0],
        )
        cross_magnitude = math.sqrt(sum(component**2 for component in cross_product))
        assert cross_magnitude > 0.0, "Triangle must have non-zero area"

        # Direction of cross product must match facet normal
        dot_product = (
            normal[0] * cross_product[0]
            + normal[1] * cross_product[1]
            + normal[2] * cross_product[2]
        )
        assert dot_product > 0.0, (
            "Facet normal must point in direction of right-hand vertex winding"
        )


def test_step_file_referential_integrity():
    """Verify that every entity in the generated STEP file has valid references without dangling IDs."""
    instances = [
        TemplateInstance(
            id="leg_box",
            template="box",
            parameters={"length": 50.0, "width": 50.0, "height": 300.0},
            position=Vector3(x=100.0, y=100.0, z=0.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
        TemplateInstance(
            id="round_pin",
            template="cylinder",
            parameters={"diameter": 20.0, "height": 80.0},
            position=Vector3(x=0.0, y=0.0, z=300.0),
            rotation=Vector3(x=0.0, y=0.0, z=0.0),
        ),
    ]
    layout = generate_layout(instances)
    step_text = layout.to_step("MultiPartAssembly")

    parsed_step = parse_step_file(step_text)
    entities = parsed_step["entities"]
    referenced_ids = parsed_step["referenced_ids"]

    assert len(entities) > 0, "DATA section must contain entities"

    # Referential integrity check: every referenced ID must be a defined entity ID
    for referenced_id in referenced_ids:
        assert referenced_id in entities, (
            f"Dangling reference: #{referenced_id} is referenced but not defined!"
        )

    # Count solids
    solid_entities = [
        entity_id
        for entity_id, entity in entities.items()
        if entity["type"] == "MANIFOLD_SOLID_BREP"
    ]
    assert len(solid_entities) == 2, "Must contain exactly 2 MANIFOLD_SOLID_BREP solids"


def test_table_step_and_stl_boundary_coordinates():
    """Verify that coordinates written into both STL and STEP files precisely reflect the 5-box table dimensions."""
    table_instances = [
        TemplateInstance(
            id="table_top",
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

    layout = generate_layout(table_instances)

    # 1. Validate STL
    stl_content = layout.to_stl("kitchen_table")
    parsed_stl = parse_ascii_stl(stl_content)
    assert len(parsed_stl["facets"]) == 60, "5 boxes * 12 triangles = 60 triangles"

    stl_all_vertices = [
        vertex for facet in parsed_stl["facets"] for vertex in facet["vertices"]
    ]
    stl_min_x = min(vertex[0] for vertex in stl_all_vertices)
    stl_max_x = max(vertex[0] for vertex in stl_all_vertices)
    stl_min_y = min(vertex[1] for vertex in stl_all_vertices)
    stl_max_y = max(vertex[1] for vertex in stl_all_vertices)
    stl_min_z = min(vertex[2] for vertex in stl_all_vertices)
    stl_max_z = max(vertex[2] for vertex in stl_all_vertices)

    assert math.isclose(stl_min_x, -1000.0, abs_tol=1e-3)
    assert math.isclose(stl_max_x, 1000.0, abs_tol=1e-3)
    assert math.isclose(stl_min_y, -450.0, abs_tol=1e-3)
    assert math.isclose(stl_max_y, 450.0, abs_tol=1e-3)
    assert math.isclose(stl_min_z, 0.0, abs_tol=1e-3)
    assert math.isclose(stl_max_z, 750.0, abs_tol=1e-3)

    # 2. Validate STEP
    step_content = layout.to_step("kitchen_table")
    parsed_step = parse_step_file(step_content)
    entities = parsed_step["entities"]

    step_points = [
        [
            float(coordinate)
            for coordinate in re.findall(r"[-+]?\d*\.?\d+", entity["raw_body"])
        ]
        for entity in entities.values()
        if entity["type"] == "CARTESIAN_POINT"
        and "CARTESIAN_POINT('',(" in entity["raw_body"]
    ]
    assert len(step_points) >= 30, "Table must have at least 30 point definitions"

    step_min_x = min(point[0] for point in step_points)
    step_max_x = max(point[0] for point in step_points)
    step_min_y = min(point[1] for point in step_points)
    step_max_y = max(point[1] for point in step_points)
    step_min_z = min(point[2] for point in step_points)
    step_max_z = max(point[2] for point in step_points)

    assert math.isclose(step_min_x, -1000.0, abs_tol=1e-3)
    assert math.isclose(step_max_x, 1000.0, abs_tol=1e-3)
    assert math.isclose(step_min_y, -450.0, abs_tol=1e-3)
    assert math.isclose(step_max_y, 450.0, abs_tol=1e-3)
    assert math.isclose(step_min_z, 0.0, abs_tol=1e-3)
    assert math.isclose(step_max_z, 750.0, abs_tol=1e-3)


def test_file_persistence_on_disk(tmp_path: Path):
    """Verify that STL and STEP files can be written to disk, re-read and parsed without data loss."""
    box_instance = TemplateInstance(
        id="disk_test_box",
        template="box",
        parameters={"length": 80.0, "width": 40.0, "height": 20.0},
        position=Vector3(x=5.0, y=10.0, z=15.0),
        rotation=Vector3(x=0.0, y=0.0, z=0.0),
    )
    layout = generate_layout([box_instance])

    # 1. Write STL to disk
    stl_file_path = tmp_path / "model.stl"
    stl_content = layout.to_stl("disk_box")
    stl_file_path.write_text(stl_content, encoding="utf-8")

    assert stl_file_path.is_file()
    assert stl_file_path.stat().st_size > 0
    read_stl = stl_file_path.read_text(encoding="utf-8")
    parsed_disk_stl = parse_ascii_stl(read_stl)
    assert len(parsed_disk_stl["facets"]) == 12

    # 2. Write STEP to disk
    step_file_path = tmp_path / "model.step"
    step_content = layout.to_step("disk_box")
    step_file_path.write_text(step_content, encoding="utf-8")

    assert step_file_path.is_file()
    assert step_file_path.stat().st_size > 0
    read_step = step_file_path.read_text(encoding="utf-8")
    parsed_disk_step = parse_step_file(read_step)
    assert len(parsed_disk_step["entities"]) > 0


def test_empty_layout_generates_valid_empty_files():
    """Verify that an empty model layout generates valid empty STL and STEP files without crashing."""
    empty_layout = generate_layout([])

    # Empty STL
    stl_content = empty_layout.to_stl("empty")
    parsed_stl = parse_ascii_stl(stl_content)
    assert parsed_stl["solid_name"] == "empty"
    assert len(parsed_stl["facets"]) == 0

    # Empty STEP
    step_content = empty_layout.to_step("empty")
    parsed_step = parse_step_file(step_content)
    assert len(parsed_step["entities"]) > 0
    solid_ids = [
        eid
        for eid, entity in parsed_step["entities"].items()
        if entity["type"] == "MANIFOLD_SOLID_BREP"
    ]
    assert len(solid_ids) == 0
