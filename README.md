# Windows 安装 MCP for Blender

将一次 Windows 上的安装过程整理为可复用的 PowerShell 脚本：安装 `uv`、安装并启用 Blender 插件，以及为 Codex 注册 MCP 服务。

这是社区安装辅助脚本，与 Blender、OpenAI 或 MCP for Blender 官方没有隶属关系。

## 推荐：在 Blender 里点击安装

Windows 用户可以直接使用 [blender-mcp-installer-1.0.0.zip](dist/blender-mcp-installer-1.0.0.zip)，不需要手动运行 PowerShell 命令。

1. 下载 ZIP，**不要解压**。
2. Blender 打开 **编辑 → 偏好设置 → 插件**，在右上角菜单选择 **从磁盘安装 / Install from Disk**，选择 ZIP。
3. 启用 **MCP for Blender Installer** 并展开插件设置。
4. 保存当前场景，勾选“我已保存场景”。需要 Codex 时保留“同时配置 Codex”；使用其他客户端时取消该选项。
5. 点击 **一键安装 MCP for Blender**，等待状态提示完成。下载在后台进行，保持 Blender 打开且不要禁用安装助手。
6. 完全重启 Codex / VS Code。Blender 3D 视图按 `N`，检查 **MCP for Blender** 标签中的服务器状态。

首次导入安装助手 ZIP 仍需手动完成，之后的依赖下载、MCP 插件安装、启用和偏好设置保存由按钮完成。该助手使用当前 Blender 的用户插件目录，不会启动第二个 Blender 来覆盖正在使用的偏好设置。

安装助手当前只支持 Windows。若目标 MCP 插件已经启用，它会提示无需重复安装；更新请使用上游提供的更新方式。已有 Codex `blender` 注册项会保留，不保证其配置正确。安装失败可能已经完成部分步骤，请根据状态信息修复并重试。安装成功后可以禁用或移除 **Installer** 助手，保留目标 **MCP for Blender** 插件。

公开包仅包含安装助手源码和许可证，不包含个人配置、日志或上游插件。它会联网下载执行时解析的上游版本；使用前可以审阅 `addon/blender_mcp_installer/__init__.py`。安装按钮可能运行 Astral 官方 PowerShell 安装脚本，但不更改持久执行策略。

重新生成发布 ZIP：

```powershell
python .\build_addon.py
```

下文 PowerShell 方案仍可作为独立安装方式使用。

## 验证范围

原始流程已在 **Windows + Blender 5.2.2 LTS + Codex CLI** 上完成安装，并通过本地 `get_addon_info` 握手验证。仓库脚本由该流程整理而来，已做 PowerShell 语法检查；它并未在一台全新 Windows 机器上完整重装验证。其他 Blender 版本的兼容性取决于上游插件。

## 准备

- Windows PowerShell 5.1 或更新版本。
- 已安装 Blender，并知道 `blender.exe` 的完整路径。
- 默认同时配置 Codex，需要 `codex` 命令可用；其他客户端可用 `-SkipCodex` 跳过。
- 可以访问 Astral、GitHub 和 Python 包源。首次运行可能需要下载较多依赖。
- **保存工作并关闭全部 Blender 窗口**，脚本会通过后台 Blender 保存插件启用状态。

## 使用

下载本仓库，在脚本所在文件夹打开 PowerShell。将示例路径改成自己的 Blender 安装路径。

先检查环境，不修改安装或配置：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-BlenderMCP.ps1 -BlenderPath 'D:\Apps\Blender\blender.exe' -CheckOnly
```

安装插件并配置 Codex：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-BlenderMCP.ps1 -BlenderPath 'D:\Apps\Blender\blender.exe'
```

仅安装 Blender 插件：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-BlenderMCP.ps1 -BlenderPath 'D:\Apps\Blender\blender.exe' -SkipCodex
```

如果 `blender.exe` 已在 PATH 中，可以省略 `-BlenderPath`。命令中的执行策略仅对本次 PowerShell 进程生效，不修改持久策略。

## 脚本做了什么

1. 检查 Blender 路径、运行状态和 Codex 命令。
2. 查找 `uvx.exe`；缺失时下载并运行 Astral 官方 `uv` 安装脚本。
3. 通过指定的 Blender 查询其用户插件和配置目录，避免写错版本。
4. 备份已有 `blender_mcp.py` 和 `userpref.blend`，再调用上游 `install-addon` 安装插件。
5. 在后台启用 `blender_mcp` 并保存偏好设置，不修改场景文件。
6. 备份 Codex 配置，通过 `codex mcp add` 添加 `blender` 服务。已有同名服务会保留，并提示检查。

脚本使用 `$env:USERPROFILE`、Blender 返回的目录及可选的 `$env:CODEX_HOME`，没有硬编码作者的用户名、用户目录、密钥或个人 Codex 配置。

自动安装使用执行时包源解析到的 `mcp-for-blender` 版本，没有锁定依赖。上游更新可能改变行为；发布复现结果时请注明实际版本。

## 完成后检查

1. 打开 Blender，在 3D 视图按 `N`，打开 **MCP for Blender** 标签。
2. 插件一般会自动启动本地服务器；若未启动，点击 **Start MCP Server**。默认地址为 `127.0.0.1:9876`。
3. 完全退出并重新打开 Codex；在 VS Code 中使用时，重启 VS Code。
4. 执行以下命令检查注册项，然后让 AI 读取当前场景信息进行实际连接测试。

```powershell
codex mcp get blender
```

看到配置只代表服务已注册；实际操作还需要 Blender 打开、插件服务器运行，以及客户端成功加载 MCP。安装脚本本身不会启动 Blender 界面或执行场景操作。

## 手动安装命令

不使用此脚本时，也可以参照上游安装方式：

```powershell
winget install --id=astral-sh.uv -e
# 安装完成后重新打开 PowerShell
uvx mcp-for-blender install-addon
codex mcp add blender --env DISABLE_TELEMETRY=true -- uvx mcp-for-blender
```

随后在 Blender 的 **编辑 → 偏好设置 → 插件** 中启用 **MCP for Blender**。也可使用上游交互式向导 `uvx mcp-for-blender setup`，它可能配置多个检测到的客户端。

旧教程中的包名 `blender-mcp` 已由上游更名为 `mcp-for-blender`；新安装使用新名称。

## 常见问题

- **下载慢或失败**：检查网络，稍后重新运行。`uv` 会缓存已下载的依赖。
- **找不到 Codex**：先安装 Codex CLI，或使用 `-SkipCodex`，再按对应客户端的文档配置。
- **已有 blender 注册项**：脚本不会覆盖。先用 `codex mcp get blender` 检查，确需重建时手动执行 `codex mcp remove blender` 后重新运行安装脚本。
- **找不到 uvx**：重新打开 PowerShell 再运行。官方默认安装位置通常是当前用户的 `.local\bin`。
- **后台 Blender 报其他插件错误**：本脚本会加载已有 Blender 偏好设置，其他插件也可能输出日志。以退出码和 `MCP_ADDON_ENABLED` 为准；若无法正常启动 Blender，应先排查已有插件。
- **MCP 连接失败**：确认插件已启用、服务器运行且客户端已重启。不要另开多个客户端同时测试同一个 Blender。

## 备份和卸载

备份保存在原文件旁，名称包含 `.before-blender-mcp-` 和随机标识，便于恢复。不要把这些备份上传到仓库，它们可能含个人配置。

移除 Codex 注册项：

```powershell
codex mcp remove blender
```

在 Blender 偏好设置中禁用插件并保存，然后关闭 Blender；按实际安装目录删除用户插件目录中的 `blender_mcp.py` 即可。如需恢复偏好设置，请关闭 Blender 后将备份复制回 `userpref.blend`。`uv` 可能被其他工具共用，脚本不自动卸载它。

## 隐私与使用提示

此仓库不附带个人配置、运行日志、场景或凭据。上传 GitHub 前也不要添加这些文件。运行时打印的本地路径可能包含你的用户名，分享日志时请先脱敏。

Codex 注册项设置了 `DISABLE_TELEMETRY=true`，用于关闭上游 MCP 服务端遥测；这不代表控制所有客户端或第三方服务的数据行为。插件可在 Blender 内运行 Python，请先保存场景，并保持默认本地监听。

## 参考

- [MCP for Blender 上游项目](https://github.com/ahujasid/mcp-for-blender)
- [Astral uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)
- [Codex MCP 配置文档](https://developers.openai.com/codex/mcp)

本仓库只提供辅助脚本和文档，不包含上游插件源码。许可证见 [LICENSE](LICENSE)。
