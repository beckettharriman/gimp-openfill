# 15 operations in one GIMP session

`driver.py` runs 15 Generative Fill calls in one GIMP session on
`tests/data/test-scene.png` with DreamShaper 8 active. The rectangles are
random (seed 7). Every fifth call is a Remove object (LaMa).
`comfyui-rss-kb.txt` samples ComfyUI's resident memory every 10 s.

- 15/15 succeeded (PDB status SUCCESS), with one new layer each and no errors.
- Fills took 66 to 141 s (median 89 s); the time grows with the working size
  of wide selections. Some calls overlapped other test commands on the same
  machine. Removals took 4.6 to 5.3 s.
- No slowdown over the session. ComfyUI's RSS moved between 120 MB and
  1.2 GB and kept returning to the baseline, so nothing points to a leak.
  Metal allocations are only partly counted in RSS.
- Quality (`final.png`) is SD 1.5 on random, often thin rectangles that
  overlap earlier fills. Several fills echo the dark box they overlap or come
  out soft, matching the model limits the README already lists.
