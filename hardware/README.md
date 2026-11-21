# Hardware

| Folder | Contents |
|---|---|
| `diagrams/src/` | Python scripts that generate the wiring schematic and perfboard layout (output goes to `docs/images/`) |
| `cad/` | CAD source files for the Mini Super Nintendo / Super Famicom case (add yours here) |
| `stl/` | Print-ready STL files (add yours here) |

## Regenerating the diagrams

```bash
make diagrams
```

This needs only Python 3.

## Suggested notes to add for the case

When you add the CAD and STL files, a short list here helps builders:
- printer, material and layer height you used
- which parts need supports
- screws and any other hardware
- a licence for the models, for example CC BY-SA 4.0

The software and documentation in this repository are under the MIT licence (see the top-level `LICENSE`).
