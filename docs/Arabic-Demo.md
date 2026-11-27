# Arabic live demo (after 27 November 2026)

Stories: A1–A4, C1 in [Stories.md](./Stories.md).

## Demo script (about 3 minutes)

1. Open Nomo (English, dark theme) — existing app still works.
2. Choose **العربية** → page mirrors to right-to-left, all demo labels in Arabic.
3. Press **إرسال** with an empty input → Arabic error "يرجى كتابة وصف التصميم أولًا."
4. Click example chip **صندوق ١٠٠ مم** → send → "جارٍ الإنشاء…" → Arabic reply and result table
   (one box, 100 × 100 × 100 mm).
5. Type sample 2 (below) → show the table result; press **نسخ JSON** → "تم النسخ".
6. Turn on **ألوان مناسبة لعمى الألوان** → statuses switch to blue/orange and still show icon + text.
7. Reload → Arabic and palette setting are remembered.

Fallback: run with the mock provider (`model: "MOCK"`) if the network fails during the demo.

## Sample data

| # | Prompt (Arabic) | Meaning | Expected result |
| - | --- | --- | --- |
| 1 | صندوق ١٠٠ × ١٠٠ × ١٠٠ مم | Box 100 × 100 × 100 mm | 1 × `box` 100/100/100 |
| 2 | أسطوانة قطرها ٥٠ مم وارتفاعها ١٢٠ مم | Cylinder, diameter 50 mm, height 120 mm | 1 × `cylinder` |
| 3 | كرة نصف قطرها ٣٠ مم | Sphere, radius 30 mm | 1 × `sphere` |
| 4 | صندوق 200 × 50 × 20 مم | Box with Western digits | 1 × `box` 200/50/20 |
| 5 | (empty) | — | Arabic error message |

## Native-Arabic check

- Who: a native speaker (e.g. fellow student or university language centre), ideally from the Gulf.
- What: all strings in Stories A2/A4, the sample prompts, and the AI replies for samples 1–3.
- Record: reviewer, date, changes made. Status: **open**.

## Cultural assumptions log

| Assumption | Design consequence | Source / check | Status |
| --- | --- | --- | --- |
| Arabic UI must be right-to-left incl. mirrored layout and directional icons | `dir="rtl"`, mirror send arrow; keep JSON/code LTR | W3C qa-html-dir | Source checked |
| Saudi users read both Eastern (٠–٩) and Western (0–9) digits | Accept both in input; show Eastern digits in Arabic labels | Native-speaker check | To verify |
| Modern Standard Arabic is appropriate for UI text (not dialect) | Write all labels in MSA | Native-speaker check | To verify |
| Green has positive associations in Saudi Arabia (flag), red signals danger | Fine to use, but never as the only cue; C1 uses blue/orange | WCAG 1.4.1; native-speaker check | To verify |
| Avoid hand-gesture emoji, religious symbols, people/animal imagery in UI | Use neutral icons (✓, ⚠, spinner); review 📊 and theme moon icon | Native-speaker check | To verify |
| Metric units (mm, cm) are standard | Keep metric units, Arabic abbreviations مم / سم | Saudi Arabia uses SI | Source checked |
| Formal, polite tone expected for an investor audience | Short, polite messages ("يرجى…") | Native-speaker check | To verify |

## Guidance for developers

- W3C — Structural markup and right-to-left text in HTML: https://www.w3.org/International/questions/qa-html-dir
- W3C — Use of Color: https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html
