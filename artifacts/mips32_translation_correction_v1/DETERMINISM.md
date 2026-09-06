# Determinism

Two runs of the canonical ELF translation pipeline produce identical semantic artifacts.

## Run 1
- `ir.json`: `a4f9104b281f62d41b6d17b2bc7ec893f45f7be625ff1e204c32b509ef87b0ff`
- `sidecar.json`: `146b9ebc13ffdc0401b9ad78351b8c1994ad2440156d95362ffdfc8ce39df363`
- `module.json`: `b0f9db3d4bb7ee73b640822daea8eb8e08d6d6cdccb2e457f5c22501a35dc8f5`
- `generated.c`: `fbdc9b83b8b1a37829dbdf967dcbfbd71deabf32db68ed5dc64972f7d3a0c50d`

## Run 2
- `ir.json`: `a4f9104b281f62d41b6d17b2bc7ec893f45f7be625ff1e204c32b509ef87b0ff`
- `sidecar.json`: `146b9ebc13ffdc0401b9ad78351b8c1994ad2440156d95362ffdfc8ce39df363`
- `module.json`: `b0f9db3d4bb7ee73b640822daea8eb8e08d6d6cdccb2e457f5c22501a35dc8f5`
- `generated.c`: `fbdc9b83b8b1a37829dbdf967dcbfbd71deabf32db68ed5dc64972f7d3a0c50d`

## Result
Result: `PASS`
