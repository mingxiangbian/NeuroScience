# Brain Model Attribution

- Asset: Detailed Human Brain Model (3D), 3DPX-021161
- Source: NIH 3D, https://3d.nih.gov/entries/3DPX-021161
- Creator listed by NIH 3D: Johnson J
- License listed by NIH 3D: CC-BY
- Local file: `assets/brain-human.glb`

## Local optimization

- Optimized on 2026-07-16 for the homepage without mesh simplification or triangle decimation.
- Preserved 4 meshes, 215,601 position vertices, 1,133,103 indices, and 377,701 triangles.
- Converted the source specular-glossiness material metadata to standard metallic-roughness, then applied 16-bit position/normal quantization and Meshopt medium compression.
- The optimized file uses `EXT_meshopt_compression` and `KHR_mesh_quantization`; the homepage configures Three.js `MeshoptDecoder` before loading it.
