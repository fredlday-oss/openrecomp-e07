# OpenRecomp Phase 16 Fixture Policy

The private Hercules commercial fixture is located at:
`fixtures/psx/hercules/`

Fixtures:
1. `Disney's Hercules Action Game (USA).bin`:
   - Size: 409,452,624 bytes
   - SHA-256: `2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365`
2. `Disney's Hercules Action Game (USA).cue`:
   - Size: 101 bytes
   - SHA-256: `beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2`
3. `SLUS_005.29`:
   - Size: 129,024 bytes
   - SHA-256: `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`

Policy:
- The private fixture files remain untracked by Git.
- Never commit fixture files or derived binary slices into Git.
- Verification tests use read-only streaming from the private fixture path.
- Public tests use synthetic unit mock objects.
