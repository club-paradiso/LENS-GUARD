# UI implementation direction

The built-in Image Gen concept (`design-concept.png`) established the structural reference: a white research instrument with an understated side rail, green measurement graphics, an amber simulation notice, an evidence table and a selected-source inspector.

Tokens: canvas #ffffff; rail #f9fbfb; ink #15202e; secondary #65738a; border #dfe5eb; green #087443; amber #a75504. Fine 1px separators, 5–6px control/panel radii and restrained 14px base UI text. Main title 35px (29px on compact screens). Identity strings use the system monospace family. Lucide icons retain a consistent outline style; source type is never inferred from an icon.

Layout: 220px rail and a flexible main surface; horizontal metrics; chart; roughly 60/40 table/inspector split. At compact widths the rail becomes top navigation; the table and inspector stack. Chart coordinates follow its real rendered width to preserve readable mobile labels. All controls and data are native HTML/React/SVG, with keyboard focus states and semantic labels. No external fonts or media requests are needed.

Allowed copy changes from the visual concept: observed sources instead of asserted physical devices; pseudonyms instead of MACs; experimental 0–100 score; unknown/declared/synthetic file provenance; 1 Hz simulation and explicitly labeled replay; parser visibility and limitations. Mock metrics and curve shapes are replaced by actual engine output. See VALIDATION.md for the final visual comparison ledger.
