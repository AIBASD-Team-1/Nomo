# Nomo Specification

Draft 0.1 · 16 October 2026

## Purpose

Nomo turns a text prompt into a 3D model built only from **templates**. The AI chooses templates and parameter values. It never writes geometry.

*Nomo*: from Greek *nómos*, "law".

## Concepts

- **Template**: a parametric part. It has:
  - `id`, `name`, `description`. The description is what the AI reads to decide when to use the template.
  - optional `standards`: human-readable company requirements that the AI must follow and report when a request cannot satisfy them.
  - `parameters`: each with `name`, `unit`, `default`, `min`, `max`.
  - `rules`: conditions over its parameters that must hold, each with a message for the user.
  - exactly one of:
    - `geometry`: a function from parameter values to a solid, implemented with build123d;
    - `base`: the id of another template. The new template narrows the base's parameters (defaults, ranges) and adds rules, but reuses its geometry.
- **Instance**: one use of a template in a model. It has `id`, `template`, `parameters` (missing values take the default), `position` (x, y, z) and `rotation` (x, y, z in degrees, default 0).
- **Model**: a list of instances. The AI produces it, the user iterates on it, and Nomo builds geometry from it.

Every kind of part becomes a template behind this one contract: generic shapes, standard parts (screws, bolts), purchased units (gear drives) and company parts. Only the geometry differs.

## Conventions

- Units are millimetres. Z points up.
- Each template defines its origin. An instance is first rotated about that origin by `rotation`: about the fixed X axis, then Y, then Z, by the right-hand rule. It is then placed by translating the origin to `position`.

## Templates in this version

### `box`

| Parameter | Unit | Default | Min | Max |
| --- | --- | --- | --- | --- |
| `length` (along X) | mm | 100 | 1 | 10000 |
| `width` (along Y) | mm | 100 | 1 | 10000 |
| `height` (along Z) | mm | 100 | 1 | 10000 |

- **Origin:** centre of the bottom face.
- **Rules:** none beyond the ranges.
- **Geometry:** `Box(length, width, height, align=(Align.CENTER, Align.CENTER, Align.MIN))`.

## Behaviour

1. **Validate.** A model is valid when all of the following hold:
   - every instance names an existing template;
   - every parameter it sets exists in that template;
   - every value is a number within the template's range;
   - `position` and `rotation` hold numbers for x, y and z only;
   - every rule of the template and of its bases holds.

   Each violation reports the instance id, the template id, the parameter (if any) and a message.
2. **Build.** A valid model becomes one compound solid, with each instance's geometry rotated and placed at its position. Invalid models are not built.
3. **Export.** The built model is exported as a STEP file for download and as a mesh for the 3D view in the browser.
4. **Generate.**
   - **Input:** the user's prompt, the current model (possibly empty) and the template catalog: each template's id, name, description, standards, parameters and rules.
   - **Output:** one JSON object with exactly `reply` (a string) and `model` (an array). Each model instance has exactly `id`, `template`, `parameters`, `position` and `rotation`; the position and rotation each contain numeric `x`, `y` and `z` values.
   - The AI may only use templates from the catalog.
   - The AI treats template standards, including inherited standards, as mandatory. If a request conflicts with a standard, it makes a compliant adjustment when feasible and explains the standard and change in `reply`. Otherwise it returns an empty model and explains why the request cannot be fulfilled; it must not bypass a standard by choosing another template or free geometry.
   - **Response format repair:** malformed JSON or a response that does not match this structure is sent back to the AI with its validation error. There are at most 10 calls total. If none produces a valid response, the user sees an error and receives no invalid model or raw AI response.
   - **Repair:** if the new model is invalid, the violations go back to the AI to fix, for up to 3 attempts. The reply tells the user about any rule that changed their request. If the model is still invalid after the last attempt, the current model stays unchanged and the user sees the violations.
   - **No fit:** if no template fits the request, the AI says so and the model stays unchanged.

## Acceptance examples

| Given | Expect |
| --- | --- |
| One `box` with default parameters | A 100 × 100 × 100 mm solid, volume 1,000,000 mm³ |
| A `box` with `length = 0` | Violation: `length` must be at least 1 |
| An instance with template `sphere` | Violation: unknown template |
| A `box` with parameter `depth` | Violation: unknown parameter |
| A table of five `box` instances: top 2000 × 900 × 27 at (0, 0, 723), and legs 70 × 70 × 723 at (±965, ±415, 0) | A STEP file with 5 solids and a bounding box of 2000 × 900 × 750 mm |
| Template `table-top` with `base: box` and rule `length <= 1200 or height >= 25` ("Table tops longer than 1200 mm must be at least 25 mm thick"), used with `length = 2000, height = 18` | Violation from `table-top` on `height`, with that message |
| The same `table-top` with `length = 2000, height = 27` | Valid |
| A `box` 100 × 20 × 10 with rotation (90, 0, 90) at (0, 0, 50) | Bounding box x 0…10, y −50…50, z 40…60 |

## Not yet

Connection points between parts, materials, templates other than `box`, and native CAD file formats.
