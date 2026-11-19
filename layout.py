"""Server-side 3D layout generation for parametric templates (STL and STEP export)."""

import math
from datetime import datetime, timezone
from typing import Any

from catalog import TemplateInstance, Vector3


class BoundingBox:
    """Axis-aligned 3D bounding box."""

    def __init__(
        self,
        minimum_x: float,
        minimum_y: float,
        minimum_z: float,
        maximum_x: float,
        maximum_y: float,
        maximum_z: float,
    ):
        self.minimum_x = minimum_x
        self.minimum_y = minimum_y
        self.minimum_z = minimum_z
        self.maximum_x = maximum_x
        self.maximum_y = maximum_y
        self.maximum_z = maximum_z

    @property
    def size_x(self) -> float:
        return self.maximum_x - self.minimum_x

    @property
    def size_y(self) -> float:
        return self.maximum_y - self.minimum_y

    @property
    def size_z(self) -> float:
        return self.maximum_z - self.minimum_z

    def to_dict(self) -> dict[str, Any]:
        return {
            "min": {
                "x": round(self.minimum_x, 4),
                "y": round(self.minimum_y, 4),
                "z": round(self.minimum_z, 4),
            },
            "max": {
                "x": round(self.maximum_x, 4),
                "y": round(self.maximum_y, 4),
                "z": round(self.maximum_z, 4),
            },
            "size": {
                "x": round(self.size_x, 4),
                "y": round(self.size_y, 4),
                "z": round(self.size_z, 4),
            },
        }


class Triangle:
    """Triangular face with normal vector for STL generation."""

    def __init__(
        self,
        vertex_1: tuple[float, float, float],
        vertex_2: tuple[float, float, float],
        vertex_3: tuple[float, float, float],
        normal: tuple[float, float, float] | None = None,
    ):
        self.vertex_1 = vertex_1
        self.vertex_2 = vertex_2
        self.vertex_3 = vertex_3
        if normal is None:
            self.normal = compute_face_normal(vertex_1, vertex_2, vertex_3)
        else:
            self.normal = normal


class PlanarFace:
    """Planar polygonal face for STEP BREP export."""

    def __init__(
        self,
        vertices: list[tuple[float, float, float]],
        normal: tuple[float, float, float] | None = None,
    ):
        self.vertices = vertices
        if normal is None and len(vertices) >= 3:
            self.normal = compute_face_normal(
                vertices[0], vertices[1], vertices[2]
            )
        else:
            self.normal = normal or (0.0, 0.0, 1.0)


class SolidGeometry:
    """Concrete solid geometry for a single template instance."""

    def __init__(
        self,
        instance_id: str,
        template_id: str,
        faces: list[PlanarFace],
        triangles: list[Triangle],
        bounding_box: BoundingBox,
        volume: float,
    ):
        self.instance_id = instance_id
        self.template_id = template_id
        self.faces = faces
        self.triangles = triangles
        self.bounding_box = bounding_box
        self.volume = volume


class ModelLayout:
    """Compound layout containing all solids in a model."""

    def __init__(self, solids: list[SolidGeometry]):
        self.solids = solids
        self.bounding_box = compute_compound_bounding_box(solids)
        total_volume = sum(solid.volume for solid in solids)
        self.total_volume = total_volume

    def to_stl(self, solid_name: str = "nomo_layout") -> str:
        """Export layout as ASCII STL format."""
        stl_lines = [f"solid {solid_name}"]
        for solid in self.solids:
            for triangle in solid.triangles:
                normal_x, normal_y, normal_z = triangle.normal
                stl_lines.append(
                    f"  facet normal {normal_x:.6e} {normal_y:.6e} {normal_z:.6e}"
                )
                stl_lines.append("    outer loop")
                for vertex in (
                    triangle.vertex_1,
                    triangle.vertex_2,
                    triangle.vertex_3,
                ):
                    vertex_x, vertex_y, vertex_z = vertex
                    stl_lines.append(
                        f"      vertex {vertex_x:.6f} {vertex_y:.6f} {vertex_z:.6f}"
                    )
                stl_lines.append("    endloop")
                stl_lines.append("  endfacet")
        stl_lines.append(f"endsolid {solid_name}")
        return "\n".join(stl_lines) + "\n"

    def to_step(self, model_name: str = "nomo_model") -> str:
        """Export layout as ISO 10303-21 STEP format with faceted BREP solids."""
        return generate_step_content(self.solids, model_name)


def compute_face_normal(
    vertex_1: tuple[float, float, float],
    vertex_2: tuple[float, float, float],
    vertex_3: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Compute normalized cross product of vectors (v2 - v1) and (v3 - v1)."""
    edge_1_x = vertex_2[0] - vertex_1[0]
    edge_1_y = vertex_2[1] - vertex_1[1]
    edge_1_z = vertex_2[2] - vertex_1[2]

    edge_2_x = vertex_3[0] - vertex_1[0]
    edge_2_y = vertex_3[1] - vertex_1[1]
    edge_2_z = vertex_3[2] - vertex_1[2]

    cross_x = edge_1_y * edge_2_z - edge_1_z * edge_2_y
    cross_y = edge_1_z * edge_2_x - edge_1_x * edge_2_z
    cross_z = edge_1_x * edge_2_y - edge_1_y * edge_2_x

    length = math.sqrt(cross_x * cross_x + cross_y * cross_y + cross_z * cross_z)
    if length <= 1e-9:
        return (0.0, 0.0, 1.0)

    return (cross_x / length, cross_y / length, cross_z / length)


def transform_point(
    point: tuple[float, float, float],
    rotation: Vector3 | dict[str, float],
    position: Vector3 | dict[str, float],
) -> tuple[float, float, float]:
    """
    Apply rotation about fixed X, then Y, then Z axis, followed by translation.

    Conventions per Spec.md:
    Rotation in degrees about fixed X, then Y, then Z by right-hand rule.
    Translation moves the template origin to position.
    """
    rotation_x_deg = rotation.x if isinstance(rotation, Vector3) else rotation.get("x", 0.0)
    rotation_y_deg = rotation.y if isinstance(rotation, Vector3) else rotation.get("y", 0.0)
    rotation_z_deg = rotation.z if isinstance(rotation, Vector3) else rotation.get("z", 0.0)

    position_x = position.x if isinstance(position, Vector3) else position.get("x", 0.0)
    position_y = position.y if isinstance(position, Vector3) else position.get("y", 0.0)
    position_z = position.z if isinstance(position, Vector3) else position.get("z", 0.0)

    angle_x = math.radians(rotation_x_deg)
    angle_y = math.radians(rotation_y_deg)
    angle_z = math.radians(rotation_z_deg)

    initial_x, initial_y, initial_z = point

    # 1. Rotate about fixed X axis
    cos_x = math.cos(angle_x)
    sin_x = math.sin(angle_x)
    step1_x = initial_x
    step1_y = initial_y * cos_x - initial_z * sin_x
    step1_z = initial_y * sin_x + initial_z * cos_x

    # 2. Rotate about fixed Y axis
    cos_y = math.cos(angle_y)
    sin_y = math.sin(angle_y)
    step2_x = step1_x * cos_y + step1_z * sin_y
    step2_y = step1_y
    step2_z = -step1_x * sin_y + step1_z * cos_y

    # 3. Rotate about fixed Z axis
    cos_z = math.cos(angle_z)
    sin_z = math.sin(angle_z)
    step3_x = step2_x * cos_z - step2_y * sin_z
    step3_y = step2_x * sin_z + step2_y * cos_z
    step3_z = step2_z

    # 4. Translate by position
    final_x = step3_x + position_x
    final_y = step3_y + position_y
    final_z = step3_z + position_z

    return (final_x, final_y, final_z)


def compute_points_bounding_box(
    points: list[tuple[float, float, float]],
) -> BoundingBox:
    if not points:
        return BoundingBox(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)
    minimum_z = min(point[2] for point in points)
    maximum_z = max(point[2] for point in points)

    return BoundingBox(
        minimum_x=minimum_x,
        minimum_y=minimum_y,
        minimum_z=minimum_z,
        maximum_x=maximum_x,
        maximum_y=maximum_y,
        maximum_z=maximum_z,
    )


def compute_compound_bounding_box(solids: list[SolidGeometry]) -> BoundingBox:
    if not solids:
        return BoundingBox(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    minimum_x = min(solid.bounding_box.minimum_x for solid in solids)
    maximum_x = max(solid.bounding_box.maximum_x for solid in solids)
    minimum_y = min(solid.bounding_box.minimum_y for solid in solids)
    maximum_y = max(solid.bounding_box.maximum_y for solid in solids)
    minimum_z = min(solid.bounding_box.minimum_z for solid in solids)
    maximum_z = max(solid.bounding_box.maximum_z for solid in solids)

    return BoundingBox(
        minimum_x=minimum_x,
        minimum_y=minimum_y,
        minimum_z=minimum_z,
        maximum_x=maximum_x,
        maximum_y=maximum_y,
        maximum_z=maximum_z,
    )


def build_box_solid(
    parameters: dict[str, float],
    position: Vector3 | dict[str, float],
    rotation: Vector3 | dict[str, float],
    instance_id: str,
) -> SolidGeometry:
    """
    Construct a box solid.

    Origin is centre of the bottom face; length along X, width along Y, height along Z.
    """
    length = parameters.get("length", 100.0)
    width = parameters.get("width", 100.0)
    height = parameters.get("height", 100.0)

    half_length = length / 2.0
    half_width = width / 2.0

    min_x = -half_length
    max_x = half_length
    min_y = -half_width
    max_y = half_width
    min_z = 0.0
    max_z = height

    # 6 local quad faces oriented CCW when viewed from outside
    local_faces: list[list[tuple[float, float, float]]] = [
        # Bottom face (-Z)
        [
            (min_x, min_y, min_z),
            (min_x, max_y, min_z),
            (max_x, max_y, min_z),
            (max_x, min_y, min_z),
        ],
        # Top face (+Z)
        [
            (min_x, min_y, max_z),
            (max_x, min_y, max_z),
            (max_x, max_y, max_z),
            (min_x, max_y, max_z),
        ],
        # Front face (-Y)
        [
            (min_x, min_y, min_z),
            (max_x, min_y, min_z),
            (max_x, min_y, max_z),
            (min_x, min_y, max_z),
        ],
        # Back face (+Y)
        [
            (min_x, max_y, min_z),
            (min_x, max_y, max_z),
            (max_x, max_y, max_z),
            (max_x, max_y, min_z),
        ],
        # Left face (-X)
        [
            (min_x, min_y, min_z),
            (min_x, min_y, max_z),
            (min_x, max_y, max_z),
            (min_x, max_y, min_z),
        ],
        # Right face (+X)
        [
            (max_x, min_y, min_z),
            (max_x, max_y, min_z),
            (max_x, max_y, max_z),
            (max_x, min_y, max_z),
        ],
    ]

    transformed_faces: list[PlanarFace] = []
    triangles: list[Triangle] = []
    all_transformed_points: list[tuple[float, float, float]] = []

    for face_vertices in local_faces:
        transformed_face_points = [
            transform_point(vertex, rotation, position) for vertex in face_vertices
        ]
        all_transformed_points.extend(transformed_face_points)
        normal = compute_face_normal(
            transformed_face_points[0],
            transformed_face_points[1],
            transformed_face_points[2],
        )
        planar_face = PlanarFace(vertices=transformed_face_points, normal=normal)
        transformed_faces.append(planar_face)

        # Split quad into two triangles: (0, 1, 2) and (0, 2, 3)
        triangle_1 = Triangle(
            vertex_1=transformed_face_points[0],
            vertex_2=transformed_face_points[1],
            vertex_3=transformed_face_points[2],
            normal=normal,
        )
        triangle_2 = Triangle(
            vertex_1=transformed_face_points[0],
            vertex_2=transformed_face_points[2],
            vertex_3=transformed_face_points[3],
            normal=normal,
        )
        triangles.append(triangle_1)
        triangles.append(triangle_2)

    bounding_box = compute_points_bounding_box(all_transformed_points)
    volume = length * width * height

    return SolidGeometry(
        instance_id=instance_id,
        template_id="box",
        faces=transformed_faces,
        triangles=triangles,
        bounding_box=bounding_box,
        volume=volume,
    )


def build_cylinder_solid(
    parameters: dict[str, float],
    position: Vector3 | dict[str, float],
    rotation: Vector3 | dict[str, float],
    instance_id: str,
    segments: int = 32,
) -> SolidGeometry:
    """
    Construct a circular cylinder solid.

    Origin is centre of the bottom face; axis along Z.
    """
    diameter = parameters.get("diameter", 100.0)
    height = parameters.get("height", 100.0)
    radius = diameter / 2.0

    bottom_points: list[tuple[float, float, float]] = []
    top_points: list[tuple[float, float, float]] = []

    for index in range(segments):
        theta = 2.0 * math.pi * index / segments
        pos_x = radius * math.cos(theta)
        pos_y = radius * math.sin(theta)
        bottom_points.append(
            transform_point((pos_x, pos_y, 0.0), rotation, position)
        )
        top_points.append(
            transform_point((pos_x, pos_y, height), rotation, position)
        )

    bottom_center = transform_point((0.0, 0.0, 0.0), rotation, position)
    top_center = transform_point((0.0, 0.0, height), rotation, position)

    all_points = bottom_points + top_points
    bounding_box = compute_points_bounding_box(all_points)

    faces: list[PlanarFace] = []
    triangles: list[Triangle] = []

    # Bottom cap (reversed order for outward normal -Z)
    bottom_cap_vertices = list(reversed(bottom_points))
    faces.append(PlanarFace(vertices=bottom_cap_vertices))
    for index in range(segments):
        next_index = (index + 1) % segments
        triangles.append(
            Triangle(
                vertex_1=bottom_center,
                vertex_2=bottom_points[next_index],
                vertex_3=bottom_points[index],
            )
        )

    # Top cap (outward normal +Z)
    faces.append(PlanarFace(vertices=top_points))
    for index in range(segments):
        next_index = (index + 1) % segments
        triangles.append(
            Triangle(
                vertex_1=top_center,
                vertex_2=top_points[index],
                vertex_3=top_points[next_index],
            )
        )

    # Side faces
    for index in range(segments):
        next_index = (index + 1) % segments
        quad_vertices = [
            bottom_points[index],
            bottom_points[next_index],
            top_points[next_index],
            top_points[index],
        ]
        face_normal = compute_face_normal(
            quad_vertices[0], quad_vertices[1], quad_vertices[2]
        )
        faces.append(PlanarFace(vertices=quad_vertices, normal=face_normal))
        triangles.append(
            Triangle(
                vertex_1=quad_vertices[0],
                vertex_2=quad_vertices[1],
                vertex_3=quad_vertices[2],
                normal=face_normal,
            )
        )
        triangles.append(
            Triangle(
                vertex_1=quad_vertices[0],
                vertex_2=quad_vertices[2],
                vertex_3=quad_vertices[3],
                normal=face_normal,
            )
        )

    volume = math.pi * radius * radius * height

    return SolidGeometry(
        instance_id=instance_id,
        template_id="cylinder",
        faces=faces,
        triangles=triangles,
        bounding_box=bounding_box,
        volume=volume,
    )


def build_sphere_solid(
    parameters: dict[str, float],
    position: Vector3 | dict[str, float],
    rotation: Vector3 | dict[str, float],
    instance_id: str,
    rings: int = 16,
    sectors: int = 24,
) -> SolidGeometry:
    """
    Construct a sphere solid.

    Origin is lowest point of the sphere; centre at height diameter / 2.
    """
    diameter = parameters.get("diameter", 100.0)
    radius = diameter / 2.0
    center_z = radius

    grid: list[list[tuple[float, float, float]]] = []
    all_points: list[tuple[float, float, float]] = []

    for ring_index in range(rings + 1):
        phi = -math.pi / 2.0 + math.pi * ring_index / rings
        ring_points: list[tuple[float, float, float]] = []
        for sector_index in range(sectors):
            theta = 2.0 * math.pi * sector_index / sectors
            pos_x = radius * math.cos(phi) * math.cos(theta)
            pos_y = radius * math.cos(phi) * math.sin(theta)
            pos_z = center_z + radius * math.sin(phi)
            transformed = transform_point((pos_x, pos_y, pos_z), rotation, position)
            ring_points.append(transformed)
            all_points.append(transformed)
        grid.append(ring_points)

    bounding_box = compute_points_bounding_box(all_points)
    faces: list[PlanarFace] = []
    triangles: list[Triangle] = []

    for ring_index in range(rings):
        for sector_index in range(sectors):
            next_sector = (sector_index + 1) % sectors

            bottom_left = grid[ring_index][sector_index]
            bottom_right = grid[ring_index][next_sector]
            top_left = grid[ring_index + 1][sector_index]
            top_right = grid[ring_index + 1][next_sector]

            if ring_index == 0:
                triangle = Triangle(bottom_left, bottom_right, top_right)
                triangles.append(triangle)
                faces.append(PlanarFace(vertices=[bottom_left, bottom_right, top_right]))
            elif ring_index == rings - 1:
                triangle = Triangle(bottom_left, top_right, top_left)
                triangles.append(triangle)
                faces.append(PlanarFace(vertices=[bottom_left, top_right, top_left]))
            else:
                triangle_1 = Triangle(bottom_left, bottom_right, top_right)
                triangle_2 = Triangle(bottom_left, top_right, top_left)
                triangles.append(triangle_1)
                triangles.append(triangle_2)
                faces.append(PlanarFace(vertices=[bottom_left, bottom_right, top_right]))
                faces.append(PlanarFace(vertices=[bottom_left, top_right, top_left]))

    volume = (4.0 / 3.0) * math.pi * radius * radius * radius

    return SolidGeometry(
        instance_id=instance_id,
        template_id="sphere",
        faces=faces,
        triangles=triangles,
        bounding_box=bounding_box,
        volume=volume,
    )


def generate_solid(instance: TemplateInstance | dict[str, Any]) -> SolidGeometry:
    """Generate the solid geometry for one template instance."""
    if isinstance(instance, TemplateInstance):
        instance_id = instance.id
        template_id = instance.template
        parameters = instance.parameters
        position = instance.position
        rotation = instance.rotation
    else:
        instance_id = str(instance.get("id", "solid"))
        template_id = str(instance.get("template", "box"))
        parameters = instance.get("parameters", {})
        position = instance.get("position", {"x": 0.0, "y": 0.0, "z": 0.0})
        rotation = instance.get("rotation", {"x": 0.0, "y": 0.0, "z": 0.0})

    if template_id == "box":
        return build_box_solid(parameters, position, rotation, instance_id)
    if template_id == "cylinder":
        return build_cylinder_solid(parameters, position, rotation, instance_id)
    if template_id == "sphere":
        return build_sphere_solid(parameters, position, rotation, instance_id)

    # Fallback to box if an unknown template is encountered
    return build_box_solid(parameters, position, rotation, instance_id)


def generate_layout(
    instances: list[TemplateInstance] | list[dict[str, Any]],
) -> ModelLayout:
    """Generate compound 3D layout from a list of template instances."""
    solids = [generate_solid(instance) for instance in instances]
    return ModelLayout(solids=solids)


def generate_step_content(solids: list[SolidGeometry], model_name: str) -> str:
    """
    Generate an ISO 10303-21 STEP representation of the model layout.

    Produces valid CONFIG_CONTROL_DESIGN / AP203 faceted solids.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    lines: list[str] = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('Nomo CAD Model', 'Compound Solid Layout'),'2;1');",
        f"FILE_NAME('{model_name}.step','{now_utc}',('Nomo User'),('TU Graz'),'Nomo STEP Generator','Nomo CAD','');",
        "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));",
        "ENDSEC;",
        "DATA;",
    ]

    entity_id = 1

    def next_id() -> int:
        nonlocal entity_id
        current_id = entity_id
        entity_id += 1
        return current_id

    # Global context entities
    app_context_id = next_id()
    lines.append(
        f"#{app_context_id} = APPLICATION_CONTEXT('configuration controlled 3d designs of mechanical parts and assemblies');"
    )

    app_protocol_id = next_id()
    lines.append(
        f"#{app_protocol_id} = APPLICATION_PROTOCOL_DEFINITION('international standard','config_control_design',1994,#{app_context_id});"
    )

    product_context_id = next_id()
    lines.append(
        f"#{product_context_id} = PRODUCT_CONTEXT('',#{app_context_id},'mechanical');"
    )

    product_id = next_id()
    lines.append(
        f"#{product_id} = PRODUCT('{model_name}','{model_name}','Nomo CAD Generated Product', (#{product_context_id}));"
    )

    product_formation_id = next_id()
    lines.append(
        f"#{product_formation_id} = PRODUCT_DEFINITION_FORMATION('1.0','First Version',#{product_id});"
    )

    product_def_id = next_id()
    lines.append(
        f"#{product_def_id} = PRODUCT_DEFINITION('design','',#{product_formation_id},#{product_context_id});"
    )

    product_shape_id = next_id()
    lines.append(
        f"#{product_shape_id} = PRODUCT_DEFINITION_SHAPE('','',#{product_def_id});"
    )

    # Standard directions
    dir_z_id = next_id()
    lines.append(f"#{dir_z_id} = DIRECTION('',(0.,0.,1.));")
    dir_x_id = next_id()
    lines.append(f"#{dir_x_id} = DIRECTION('',(1.,0.,0.));")
    origin_point_id = next_id()
    lines.append(f"#{origin_point_id} = CARTESIAN_POINT('',(0.,0.,0.));")
    world_placement_id = next_id()
    lines.append(
        f"#{world_placement_id} = AXIS2_PLACEMENT_3D('',#{origin_point_id},#{dir_z_id},#{dir_x_id});"
    )

    solid_ids: list[int] = []

    for solid in solids:
        face_ids: list[int] = []
        for face in solid.faces:
            # 1. Cartesian points for each vertex
            vertex_point_ids: list[int] = []
            for vertex in face.vertices:
                point_id = next_id()
                lines.append(
                    f"#{point_id} = CARTESIAN_POINT('',({vertex[0]:.6f},{vertex[1]:.6f},{vertex[2]:.6f}));"
                )
                vertex_point_ids.append(point_id)

            # 2. Poly loop
            poly_loop_id = next_id()
            points_tuple_str = "(" + ",".join(f"#{pid}" for pid in vertex_point_ids) + ")"
            lines.append(f"#{poly_loop_id} = POLY_LOOP('',{points_tuple_str});")

            # 3. Face outer bound
            bound_id = next_id()
            lines.append(
                f"#{bound_id} = FACE_OUTER_BOUND('',#{poly_loop_id},.T.);"
            )

            # 4. Plane geometry
            normal_dir_id = next_id()
            norm_x, norm_y, norm_z = face.normal
            lines.append(
                f"#{normal_dir_id} = DIRECTION('',({norm_x:.6f},{norm_y:.6f},{norm_z:.6f}));"
            )

            plane_placement_id = next_id()
            first_point_id = vertex_point_ids[0]
            lines.append(
                f"#{plane_placement_id} = AXIS2_PLACEMENT_3D('',#{first_point_id},#{normal_dir_id},#{dir_x_id});"
            )

            plane_id = next_id()
            lines.append(f"#{plane_id} = PLANE('',#{plane_placement_id});")

            # 5. Advanced face
            face_id = next_id()
            lines.append(
                f"#{face_id} = ADVANCED_FACE('',(#{bound_id}),#{plane_id},.T.);"
            )
            face_ids.append(face_id)

        # Closed shell for this solid
        shell_id = next_id()
        faces_tuple_str = "(" + ",".join(f"#{fid}" for fid in face_ids) + ")"
        lines.append(f"#{shell_id} = CLOSED_SHELL('',{faces_tuple_str});")

        # Manifold solid brep
        manifold_solid_id = next_id()
        lines.append(
            f"#{manifold_solid_id} = MANIFOLD_SOLID_BREP('{solid.instance_id}',#{shell_id});"
        )
        solid_ids.append(manifold_solid_id)

    # Units and uncertainty definitions
    length_unit_id = next_id()
    lines.append(
        f"#{length_unit_id} = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );"
    )

    plane_angle_unit_id = next_id()
    lines.append(
        f"#{plane_angle_unit_id} = ( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) );"
    )

    solid_angle_unit_id = next_id()
    lines.append(
        f"#{solid_angle_unit_id} = ( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() );"
    )

    uncertainty_id = next_id()
    lines.append(
        f"#{uncertainty_id} = UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),#{length_unit_id},'distance_accuracy_value','confusion accuracy');"
    )

    # Geometric representation context
    geom_context_id = next_id()
    lines.append(
        f"#{geom_context_id} = ( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty_id})) GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length_unit_id},#{plane_angle_unit_id},#{solid_angle_unit_id})) REPRESENTATION_CONTEXT('{model_name}','3D') );"
    )

    # Shape representation collecting all solids
    shape_rep_id = next_id()
    solids_tuple_str = "(" + ",".join(f"#{sid}" for sid in solid_ids) + ")" if solid_ids else "()"
    lines.append(
        f"#{shape_rep_id} = ADVANCED_BREP_SHAPE_REPRESENTATION('{model_name}',{solids_tuple_str},#{geom_context_id});"
    )

    # Link shape to product
    shape_def_rep_id = next_id()
    lines.append(
        f"#{shape_def_rep_id} = SHAPE_DEFINITION_REPRESENTATION(#{product_shape_id},#{shape_rep_id});"
    )

    lines.append("ENDSEC;")
    lines.append("END-ISO-10303-21;")
    return "\n".join(lines) + "\n"
