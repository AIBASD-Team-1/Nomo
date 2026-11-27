# Demo video script (27 November 2026)

Two videos of the same build, about 5 minutes each, both narrated in English.
Upload as **Unlisted**, check they play signed out, submit in TeachCenter as
"English interface" and "Arabic interface" by **18:00 CET**.

Recorded: English interface — https://www.youtube.com/watch?v=Lp9IzCjM7tA
(local copy: [2026-11-27 Nomo Demo1.mp4](./2026-11-27%20Nomo%20Demo1.mp4)).

## Before recording

- `git pull` on `dev`, start `uv run --locked uvicorn main:app` with a real AI provider (not mock).
- Fresh browser window (or clear site data), zoom about 125 %, 1080p, microphone on.
- Try every prompt once. If an AI reply looks wrong while recording, cut and redo that step.

## Video 1 — English interface

| # | Do | Say |
| - | --- | --- |
| 1 | Show the start page. | "Hi, this is Nomo. Nomo turns a plain-language description into a 3D CAD model. The AI does not draw geometry itself. It only picks from tested, parametric templates and fills in the dimensions, so every part it creates is valid and can be manufactured." |
| 2 | Type `Kitchen table for six people`, press **Send**. | "Let's start with a simple everyday example. I don't need to know any dimensions. I just say what I want: a kitchen table for six people." |
| 3 | Wait for the model. Rotate and zoom the 3D view. | "Nomo fills in sensible dimensions for me — table size, height and leg thickness — explains them in the chat, and shows the model right away. It built the table from boxes: one table top and four legs. I can rotate and zoom to check the design from every side." |
| 4 | Type `Make the legs thicker`, press **Send**. | "Designs are rarely right the first time, so I can refine them in conversation. I'll ask for thicker legs. Nomo keeps the rest of the table and only changes what I asked for." |
| 5 | Type `Make the table top 10 mm thick`, press **Send**. | "Now something that breaks a rule. Each template has engineering rules — for example, a box must be thicker than 10 millimetres. I'll ask for a 10 millimetre table top. Nomo does not silently build an invalid part. It explains which rule I broke and suggests the closest valid design instead." |
| 6 | Click **JSON Table**, then **Raw JSON**, then **Copy JSON**. | "Behind the 3D view, every design is plain, validated JSON: which template, which parameters, and where each part sits. Developers can copy it with one click." |
| 7 | Click **Download STEP**. | "When the design is ready, I download it as STEP or STL and open it in any CAD tool or send it to a 3D printer." |
| 8 | Switch on **Free geometry**, type `A cone, base radius 40 mm, height 80 mm`, press **Send**. | "There is no cone template yet. If the user explicitly turns on Free geometry, Nomo can fall back to generated geometry and says so clearly in its answer. By default it stays on templates only." |
| 9 | Click the theme button. | "There is also a light and a dark theme, so Nomo is comfortable to use in any environment." |
| 10 | Go back to **3D View**. | "So that's Nomo: describe, refine, check the rules, and export. Thanks for watching." |

## Video 2 — Arabic interface

| # | Do | Say |
| - | --- | --- |
| 1 | Show the start page, click **العربية**. | "This is the Arabic interface of the same build. With one click the whole page switches to Arabic and mirrors from right to left. The chat moves to the right, text starts at the right edge, and the send arrow points left." |
| 2 | Press **إرسال** with an empty input. | "Feedback is in Arabic as well. If I send an empty prompt, Nomo asks me politely, in Modern Standard Arabic, to describe my design first." |
| 3 | Type `طاولة مطبخ لستة أشخاص`, press **إرسال**. | "Now the same example for an Arabic-speaking user. I simply type, in Arabic: a kitchen table for six people. Nomo understands it, chooses sensible dimensions, answers in Arabic, and builds the 3D model." |
| 4 | Rotate the 3D view. | "It's the same kind of model as in the English version — the language only changes the interface and the conversation, not the engineering." |
| 5 | Type `اجعل الأرجل أسمك`, press **إرسال**. | "Refining works in Arabic too. I'm asking: make the legs thicker." |
| 6 | Type `اجعل سماكة سطح الطاولة ١٠ مم`, press **إرسال**. | "And here I break the same rule as before: I ask for a 10 millimetre table top — written with Eastern Arabic digits. Nomo explains in Arabic that the box must be thicker than 10 millimetres and proposes a valid thickness." |
| 7 | Type `صندوق 200 × 50 × 20 مم`, press **إرسال**. | "Users in Saudi Arabia read both Eastern and Western digits, so this prompt with Western digits works as well." |
| 8 | Click **جدول JSON**. | "All labels are Arabic, but code and JSON stay left to right, so numbers and keys remain readable. This follows the W3C guidance for right-to-left pages." |
| 9 | Reload the page. | "After a reload, the Arabic interface is remembered, so the user doesn't have to switch again." |
| 10 | Click **تنزيل STEP**. | "And the export is the same STEP file. Thank you for watching." |

## Prompt translations (for the narrator)

| Arabic prompt | Meaning |
| --- | --- |
| طاولة مطبخ لستة أشخاص | Kitchen table for six people |
| اجعل الأرجل أسمك | Make the legs thicker |
| اجعل سماكة سطح الطاولة ١٠ مم | Make the table top 10 mm thick (breaks the rule) |
| صندوق 200 × 50 × 20 مم | Box 200 × 50 × 20 mm (Western digits) |
