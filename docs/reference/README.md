# Camera API references

`openapi-Hero13.json` is retained only as a legacy snapshot for comparison. It
must not be used to generate the active camera wrapper or UI enums.

MISSION 1 PRO support follows the current, model-filterable official
[Open GoPro HTTP specification](https://gopro.github.io/OpenGoPro/http/). The
camera's `/gopro/camera/capabilities` and `/gopro/camera/presets/get` responses
are authoritative at runtime.
