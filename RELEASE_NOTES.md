# DiceFrame v3.0.1

## 中文

### 重要修复

- 修复 Edge TTS 在微软接口启用 `Sec-MS-GEC` v2 后持续返回 HTTP 403 的问题。
- 将 `edge-tts` 运行时最低版本提高到 7.3.1，并同步更新 Docker 与 Windows 便携版的 hash 锁定依赖。

### 升级说明

- 托管 Docker 用户会在更新后使用新的 Edge TTS 依赖。
- Windows 便携版会随本版本携带 `edge-tts` 7.3.1。
- 升级重要对局前仍建议备份完整的 `data/` 文件夹。

## English

### Important fix

- Fix Edge TTS returning HTTP 403 after Microsoft's endpoint began requiring `Sec-MS-GEC` v2 tokens.
- Raise the runtime minimum to `edge-tts` 7.3.1 and update the hash-pinned Docker and Windows portable locks.

### Upgrade notes

- Managed Docker users receive the updated Edge TTS dependency with this update.
- The Windows portable build includes `edge-tts` 7.3.1.
- Back up the complete `data/` directory before upgrading important campaigns.

## Downloads

- **普通 Windows 用户**：`DiceFrame-v3.0.1-windows-portable.zip`
- **源码运行用户**：`DiceFrame-v3.0.1-windows.zip`
- **托管 Docker 更新**：`DiceFrame-v3.0.1-docker-update-linux-amd64.zip`
- Release 同时提供以上压缩包及 `SHA256SUMS` 校验文件。
