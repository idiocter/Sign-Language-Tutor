# Avatar clips

Authored glTF sign clips go here, named by language-neutral sign id:

```
nsl_0001.glb
nsl_0002.glb
...
```

Each replaces the **procedural** placeholder motion for that sign. Drop a `.glb` in and it
plugs itself in automatically — `GET /clips/manifest` flips the sign to `authored`,
`/produce` sets its `clip_ref`, and the avatar plays the clip instead of the procedural
pose. See [`docs/avatar-authoring.md`](../../../docs/avatar-authoring.md) for the Blender +
ARKit workflow.

`.glb` files are gitignored (large binaries). For production, store them in Cloudflare R2
and sync into this folder for local dev.
