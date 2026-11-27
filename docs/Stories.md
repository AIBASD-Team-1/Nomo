Prompt to model

Refine model

Show rule violations

Company template

Free geometry fallback

3D preview

STEP download
---

# Replanning: Arabic live demo (deadline 27 November 2026)

Priority 1: Arabic demo path. Priority 2: colour-blindness setting (if capacity allows).
Estimates: to be set in the planning game (Ulassa cards) — `SP: ?` below. Compare the sum
against measured velocity and the 6 remaining course hours of this week.

Demo journey (only this path must work in Arabic): open app → switch to العربية → pick an
Arabic example prompt or type one → send → read the Arabic reply and result table → see an
Arabic error when the input is empty. Everything else stays English and must keep working.

Implementation guidance:
- W3C — Structural markup and right-to-left text in HTML: https://www.w3.org/International/questions/qa-html-dir
- W3C — Use of Color (WCAG 1.4.1): https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html

## A1 Language switch (new) — SP: ?

As an Arabic-speaking user I want to switch the interface to Arabic so that I can use Nomo in my language.

```gherkin
Feature: Language switch
  Scenario: Switch to Arabic
    Given I open Nomo
    When I choose "العربية" in the language selector
    Then the page has lang="ar" and dir="rtl"
    And the header subtitle reads "اكتب وصف التصميم في نافذة المحادثة وشاهد النتيجة"
    And the language selector now offers "English"

  Scenario: Choice is remembered
    Given I chose "العربية"
    When I reload the page
    Then the interface is still in Arabic

  Scenario: English stays the default
    Given I open Nomo for the first time
    Then the page has lang="en" and dir="ltr"
```

## A2 Arabic labels and right-to-left layout (new, depends on A1) — SP: ?

As an Arabic-speaking user I want all labels on the demo path in Arabic and laid out right to left so that the page reads naturally.

| Element | English | Arabic |
| --- | --- | --- |
| Chat panel title | Chat Window | نافذة المحادثة |
| Greeting | Hello! Enter your prompt below… | مرحبًا! اكتب وصف التصميم أدناه. |
| Example label | Try: | جرّب: |
| Example chip | Box 100 mm | صندوق ١٠٠ مم |
| Example chip | Kitchen table 160 × 90 cm | طاولة مطبخ ١٦٠ × ٩٠ سم |
| Input placeholder | Enter your prompt here... | اكتب وصفك هنا... |
| Send button | Send | إرسال |
| Output panel title | Output Panel | لوحة النتائج |
| Tabs | JSON Table / Raw JSON | جدول JSON / JSON خام |
| Table headers | Key / Type / Value | المفتاح / النوع / القيمة |
| Empty state | No response yet… | لا توجد نتيجة بعد. أرسل وصفًا لعرض النتيجة. |
| Copy button | Copy JSON | نسخ JSON |
| Sender name | Nomo AI | مساعد نومو |

```gherkin
Feature: Arabic labels and RTL layout
  Scenario: Labels on the demo path are Arabic
    Given the interface is in Arabic
    Then every label in the table above shows its Arabic text

  Scenario: Layout mirrors
    Given the interface is in Arabic
    Then the chat panel is on the right and the output panel on the left
    And text in the input field starts at the right edge
    And the send arrow icon points to the left

  Scenario: Code stays left to right
    Given the interface is in Arabic
    When a result is shown
    Then the raw JSON block is displayed left to right (dir="ltr")
```

## A3 Arabic prompt input (changed "Prompt to model", depends on A1) — SP: ?

As an Arabic-speaking user I want to describe a design in Arabic so that I get a model without writing English.

```gherkin
Feature: Arabic prompt
  Scenario: Arabic prompt gives a model and an Arabic reply
    Given the interface is in Arabic
    When I send "صندوق ١٠٠ × ١٠٠ × ١٠٠ مم"
    Then the result contains one box instance with width, depth and height 100 mm
    And the assistant reply is written in Arabic

  Scenario: Eastern and Western digits are equivalent
    When I send "صندوق 100 × 100 × 100 مم"
    Then the result is the same as for "صندوق ١٠٠ × ١٠٠ × ١٠٠ مم"
```

Note for developers: the system prompt must tell the AI to answer in the user's language and to read
Eastern Arabic digits (٠–٩). The model JSON (ids, parameter names) stays English.

## A4 Arabic feedback and errors (new, depends on A1) — SP: ?

```gherkin
Feature: Arabic feedback
  Scenario: Empty input
    Given the interface is in Arabic
    When I press "إرسال" with an empty input
    Then I see "يرجى كتابة وصف التصميم أولًا."

  Scenario: Waiting
    When I send a prompt
    Then the status shows "جارٍ الإنشاء…" with a spinner icon

  Scenario: Server error
    Given the AI provider fails
    When I send a prompt
    Then I see "تعذّر إنشاء النموذج. حاول مرة أخرى." with a warning icon

  Scenario: Copied
    When I press "نسخ JSON"
    Then I see "تم النسخ" with a check icon
```

## C1 Colour-blind friendly display (new, priority 2) — SP: ?

As a user with colour-vision deficiency I want a colour-blind-safe display so that I can tell states apart.

```gherkin
Feature: Colour-blind setting
  Scenario: Turn on colour-blind-safe palette
    Given I open the display settings
    When I turn on "Colour-blind safe" ("ألوان مناسبة لعمى الألوان")
    Then status colours use the blue/orange palette (no red/green pair)
    And the choice is remembered after reload

  Scenario: Information never relies on colour alone
    Given any palette
    Then every status (ready, loading, success, error) shows an icon and a text label
    And the active tab is marked by an underline and bold text, not only colour

  Scenario: Contrast
    Given the colour-blind-safe palette in light and dark theme
    Then text contrast is at least 4.5:1
```

## Definition of Done for this replanning

- Gherkin scenarios above are automated (Arabic included), code-reviewed, PO-reviewed, merged.
- Existing English behaviour and tests still pass.
- Arabic texts checked by a native speaker (see `docs/Arabic-Demo.md`).
