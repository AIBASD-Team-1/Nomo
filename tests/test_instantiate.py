import pytest

from catalog import (
    ModelValidationError,
    Template,
    TemplateParameter,
    TemplateRule,
    instantiate_model,
    load_template_catalog,
)


def test_instantiate_box_with_default_parameters():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "box_default",
        "template": "box",
        "parameters": {},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    instantiated_instances = instantiate_model([raw_instance], catalog)

    assert len(instantiated_instances) == 1
    instance = instantiated_instances[0]
    assert instance.id == "box_default"
    assert instance.template == "box"
    assert instance.parameters == {
        "length": 100.0,
        "width": 100.0,
        "height": 100.0,
    }


def test_box_with_5mm_height_reports_rule_violation():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "box_5mm_high",
        "template": "box",
        "parameters": {"height": 5.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }

    with pytest.raises(ModelValidationError) as error_info:
        instantiate_model([raw_instance], catalog)

    violation = error_info.value.violations[0]
    assert violation.parameter == "height"
    assert violation.message == "height must be greater than 10"


def test_instantiate_box_with_partial_and_custom_parameters():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "box_custom",
        "template": "box",
        "parameters": {"length": 250.0},
        "position": {"x": 10.0, "y": 20.0, "z": 30.0},
        "rotation": {"x": 90.0, "y": 0.0, "z": 45.0},
    }
    instantiated_instances = instantiate_model([raw_instance], catalog)

    assert len(instantiated_instances) == 1
    instance = instantiated_instances[0]
    assert instance.parameters == {
        "length": 250.0,
        "width": 100.0,
        "height": 100.0,
    }
    assert instance.position.x == 10.0
    assert instance.rotation.x == 90.0


def test_instantiate_cylinder_and_sphere():
    catalog = load_template_catalog()
    model_instances = [
        {
            "id": "cyl_1",
            "template": "cylinder",
            "parameters": {"diameter": 50.0, "height": 200.0},
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        {
            "id": "sph_1",
            "template": "sphere",
            "parameters": {},
            "position": {"x": 0.0, "y": 0.0, "z": 100.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
    ]
    instantiated_instances = instantiate_model(model_instances, catalog)

    assert len(instantiated_instances) == 2
    assert instantiated_instances[0].parameters == {
        "diameter": 50.0,
        "height": 200.0,
    }
    assert instantiated_instances[1].parameters == {
        "diameter": 100.0,
    }


def test_reject_unknown_template():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "pyr_1",
        "template": "pyramid",
        "parameters": {},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    with pytest.raises(ModelValidationError) as error_info:
        instantiate_model([raw_instance], catalog)

    error_message = str(error_info.value)
    assert "Unknown template 'pyramid'" in error_message
    assert error_info.value.violations[0].instance_id == "pyr_1"
    assert error_info.value.violations[0].template_id == "pyramid"


def test_reject_unknown_parameter():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "box_1",
        "template": "box",
        "parameters": {"depth": 50.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    with pytest.raises(ModelValidationError) as error_info:
        instantiate_model([raw_instance], catalog)

    error_message = str(error_info.value)
    assert "Unknown parameter 'depth' for template 'box'" in error_message


def test_reject_parameter_below_min():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "box_1",
        "template": "box",
        "parameters": {"length": 0.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    with pytest.raises(ModelValidationError) as error_info:
        instantiate_model([raw_instance], catalog)

    error_message = str(error_info.value)
    assert "Parameter 'length' must be at least 1" in error_message


def test_reject_parameter_above_max():
    catalog = load_template_catalog()
    raw_instance = {
        "id": "box_1",
        "template": "box",
        "parameters": {"length": 20000.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    with pytest.raises(ModelValidationError) as error_info:
        instantiate_model([raw_instance], catalog)

    error_message = str(error_info.value)
    assert "Parameter 'length' must be at most 10000" in error_message


def test_template_rule_violation_and_success():
    rule_message = "Table tops longer than 1200 mm must be at least 25 mm thick"
    table_top_template = Template(
        id="table-top",
        description="Table top panel",
        base="box",
        parameters={
            "length": TemplateParameter(
                unit="mm", min=100.0, max=3000.0, default=1600.0
            ),
            "width": TemplateParameter(unit="mm", min=100.0, max=1500.0, default=900.0),
            "height": TemplateParameter(unit="mm", min=10.0, max=100.0, default=27.0),
        },
        rules=[
            TemplateRule(
                check="length <= 1200 or height >= 25",
                message=rule_message,
                parameter="height",
            )
        ],
    )
    catalog = {"table-top": table_top_template}

    # Violation case: length = 2000, height = 18
    invalid_instance = {
        "id": "top_1",
        "template": "table-top",
        "parameters": {"length": 2000.0, "height": 18.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    with pytest.raises(ModelValidationError) as error_info:
        instantiate_model([invalid_instance], catalog)

    assert rule_message in str(error_info.value)
    assert error_info.value.violations[0].parameter == "height"

    # Valid case: length = 2000, height = 27
    valid_instance = {
        "id": "top_1",
        "template": "table-top",
        "parameters": {"length": 2000.0, "height": 27.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    instantiated = instantiate_model([valid_instance], catalog)
    assert len(instantiated) == 1
    assert instantiated[0].parameters["height"] == 27.0


def test_base_template_inheritance_and_cycles(tmp_path):
    box_path = tmp_path / "box.json"
    box_path.write_text(
        """{
        "id": "box",
        "description": "Base box",
        "standards": ["Use approved material."],
        "parameters": {
            "length": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
            "width": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
            "height": {"unit": "mm", "min": 1, "max": 10000, "default": 100}
        },
        "rules": [],
        "origin": "centre of bottom"
    }""",
        encoding="utf-8",
    )
    panel_path = tmp_path / "panel.json"
    panel_path.write_text(
        """{
        "id": "panel",
        "base": "box",
        "standards": ["Panels longer than 1200 mm must be at least 25 mm thick."],
        "parameters": {
            "height": {"unit": "mm", "min": 5, "max": 50, "default": 19}
        },
        "rules": []
    }""",
        encoding="utf-8",
    )

    catalog = load_template_catalog(tmp_path)
    assert "panel" in catalog
    panel_template = catalog["panel"]
    assert panel_template.parameters["length"].default == 100.0
    assert panel_template.parameters["height"].default == 19.0
    assert panel_template.origin == "centre of bottom"
    assert panel_template.standards == [
        "Use approved material.",
        "Panels longer than 1200 mm must be at least 25 mm thick.",
    ]

    # Test circular dependency detection
    a_path = tmp_path / "cycle_a.json"
    b_path = tmp_path / "cycle_b.json"
    a_path.write_text(
        '{"id": "cycle_a", "base": "cycle_b", "parameters": {}, "rules": []}',
        encoding="utf-8",
    )
    b_path.write_text(
        '{"id": "cycle_b", "base": "cycle_a", "parameters": {}, "rules": []}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Circular template base dependency"):
        load_template_catalog(tmp_path)


def test_instantiate_five_boxes_table_model():
    """Acceptance example from Spec.md: 5 boxes forming a table."""
    catalog = load_template_catalog()
    table_model = [
        {
            "id": "top",
            "template": "box",
            "parameters": {"length": 2000.0, "width": 900.0, "height": 27.0},
            "position": {"x": 0.0, "y": 0.0, "z": 723.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        {
            "id": "leg_1",
            "template": "box",
            "parameters": {"length": 70.0, "width": 70.0, "height": 723.0},
            "position": {"x": 965.0, "y": 415.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        {
            "id": "leg_2",
            "template": "box",
            "parameters": {"length": 70.0, "width": 70.0, "height": 723.0},
            "position": {"x": -965.0, "y": 415.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        {
            "id": "leg_3",
            "template": "box",
            "parameters": {"length": 70.0, "width": 70.0, "height": 723.0},
            "position": {"x": 965.0, "y": -415.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        {
            "id": "leg_4",
            "template": "box",
            "parameters": {"length": 70.0, "width": 70.0, "height": 723.0},
            "position": {"x": -965.0, "y": -415.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
    ]

    instantiated_instances = instantiate_model(table_model, catalog)
    assert len(instantiated_instances) == 5
    assert instantiated_instances[0].id == "top"
    assert instantiated_instances[0].parameters["length"] == 2000.0
    assert instantiated_instances[1].parameters["height"] == 723.0


def test_template_instantiate_method_directly():
    catalog = load_template_catalog()
    box_template = catalog["box"]
    instance = box_template.instantiate("my_box", {"length": 150.0})

    assert instance.id == "my_box"
    assert instance.template == "box"
    assert instance.parameters == {
        "length": 150.0,
        "width": 100.0,
        "height": 100.0,
    }
