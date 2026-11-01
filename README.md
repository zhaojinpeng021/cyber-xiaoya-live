# 赛博小雅直播版 · 组件版数字人（Vidu s2）

> 📦 **配套仓库**：[赛博小雅 · 弹幕采集器]—— 抖音 / B站 / YouTube / 视频号，
> 装好并把 `tts.output` 设成 `dh` 就能把观众弹幕灌进本仓库的桥。

> ⚠️ **先说清楚：这不是"下载双击就能播"的成品。**
> 仓库里给的是**整套软件**（舞台页 + 本地桥 + 弹幕/歌单/录播全链路），
> 但**不包含**作者的人物形象、克隆音色、人设、动作库、歌库和任何 API Key —— 那些需要你自己准备。
> 这份 README 会把"从零跑起来"需要做的每一步写清楚，照着做大约 **1 小时**。

---

## 0. 你需要准备什么

| 项目 | 是否必须 | 说明 |
|---|---|---|
| Windows 10/11 + NVIDIA 显卡（≥8GB 显存） | 必须 | 渲染在云端，但 TTS 在本机跑 |
| Vidu 账号 + API Key | 必须 | 数字人渲染与推流，按秒计费（1 积分/秒） |
| LLM API Key（DeepSeek 或任意 OpenAI 兼容） | 必须 | 她的"脑子" |
| TTS 服务（OmniVoice / 见 §2.4） | 必须，否则没声音 | 本机跑，WSL2 + CUDA |
| ffmpeg | 必须 | 音频解码统一走它 |
| 弹幕采集器（抖音/B站/YouTube） | 可选 | 不装就只能手动打字互动 |
| 点播歌库 | 可选 | 不放歌就没有点播 |
| 摄像头/推流软件（OBS 等） | 可选 | 想把画面推给平台才需要 |

---

## 1. 它到底是怎么跑起来的

```
浏览器「舞台页」 ──文字──▶ 本地桥(FastAPI :8795) ──type9──▶ Vidu 云端
     ▲                        │
     │                   LLM 流式 → 分句 → TTS(本机) → PCM 流
     │                        │
     └── WebRTC 订阅画面 ◀── Vidu 渲染口型+动作 ──▶ RTC 频道
```

- **Vidu 只负责"变成画面"**：给文字/音频，它渲染口型、表情、动作并推流
- **其余全在本机**：LLM 思考、TTS 发声、弹幕处理、点播、录播下载
- 舞台页是本地网页（`http://127.0.0.1:8795/stage`），你在浏览器里操作，不需要公网

**为什么这么设计**：不用买云端 ASR/LLM/TTS 套餐，成本只剩 Vidu 的渲染费；音色、人设、歌单全在你自己手里。

---

## 2. 准备工作（照着做）

### 2.1 Vidu 账号、形象、动作库

1. 注册 <https://platform.vidu.cn>，充值（按 1 积分/秒计费，余额 <45 积分开不了场）
2. 在控制台创建一个**形象**（上传一张正脸照或一段视频），记下它的 **avatar_id**
3. （可选）建一个**动作库**，往里加动作，记下 **library_id**；不建就填 `0` 用平台默认库
4. 在「API Key」页面生成 key，形如 `vda_xxx`

### 2.2 LLM API Key

默认用 DeepSeek（`https://api.deepseek.com`，模型 `deepseek-flash`）。
把 key 存成一个文本文件，路径填进 `config.json → llm.key_file`；也可以直接用环境变量 `DEEPSEEK_API_KEY`。

### 2.3 本机环境

```powershell
# 1) Python 3.12 + uv
winget install --id Python.Python.3.12
pip install uv

# 2) 装依赖
uv venv .venv --python 3.12
uv pip install -r requirements.txt --default-index https://pypi.tuna.tsinghua.edu.cn/simple

# 3) ffmpeg（作者放在 C:\ffmpeg7.1.1\bin，你也可以直接放进 PATH）
ffmpeg -version
```

### 2.4 TTS —— 这一步最容易卡住

项目**只认 OmniVoice**（`tts.engine = "omnivoice"`），因为要支持"克隆音色 + 直播中热切音色"。

#### 方案 A：OmniVoice + WSL2（推荐，作者本机就是这样跑的）

要求：WSL2 + Ubuntu-22.04 + NVIDIA 驱动 + 至少 8GB 可用显存（作者实测稳定占用 ~11GB）。

```bash
# ── 以下全部在 WSL2 的 Ubuntu-22.04 里执行 ──
sudo apt update && sudo apt install -y ffmpeg git
git clone https://github.com/k2-fsa/OmniVoice ~/omnivoice-wsl
cd ~/omnivoice-wsl

# 建环境（以官方 README 为准，作者用 Python 3.12 + torch cu13x + flashinfer）
uv venv .venv --python 3.12
uv pip install -r requirements.txt

# 下载模型 OmniVoice-bf16（HuggingFace 或 ModelScope 均可）
# 作者把模型放在 Windows 的 E 盘，WSL 里通过 /mnt/e/... 访问，不占 WSL 磁盘

# 启动服务（官方 Gradio：omnivoice-demo）
omnivoice-demo \
  --model /mnt/e/llama-models/models/OmniVoice-bf16 \
  --port 9877 --no-asr --ip 0.0.0.0 \
```

> ⚠️ `omnivoice-demo` 的参数、依赖版本可能随上游变化，**以 OmniVoice 官方 README 为准**；
> 上面的命令是作者本机实测能跑的那一份，仅作参考。

启动后从 Windows 验证：

```powershell
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9877/    # 期望 200
```

- **WSL2 镜像网络模式**下用 `127.0.0.1:9877`
- 默认 NAT 模式下用 `wsl hostname -I` 拿到的 IP，填进 `config.json → tts.omnivoice_base`
- WSL2 IP 每次重启可能变，改了要同步改配置（或者用一键脚本自动检测）

**音色从哪来**：`tts.voices_dir` 指向一个目录，里面每个子文件夹是一种音色：

| 文件夹内容 | 音色类型 | 例子 |
|---|---|---|
| `design.json` | 用属性"设计"音色（性别/年龄/音调/方言，不需要参考音频） | 御姐音 |
| `ref_audio.wav` + `ref_text.txt` + `omnivoice.txt` | 克隆音色 | 用你自己的录音克隆 |
| `ref_audio.wav` + `ref_text.txt` | 同上，少一个描述文件 | |

参考音频要求：**3–10 秒、单句、16kHz 单声道、无背景音**，`ref_text` 必须和音频逐字一致。

#### 方案 B：先不装 TTS（无声彩排）

桥没有 TTS 也能起来：舞台页能开、能连线、画面会动、字幕会滚，只是**她不会说话**。
适合先把 Vidu 链路和舞台页跑通，再回头折腾 TTS。

---

### 2.5（可选）接弹幕 —— 以抖音为例（群友最常用）

**最省事的做法**：直接用配套仓库 [赛博小雅 · 弹幕采集器]
它把抖音/B站/YouTube/视频号 四家都封装好了，`tts.output` 设成 `dh`（默认就是）即可：

```powershell
cd cyber-xiaoya-danmaku
copy config.example.json config.json      # 填房间号
.venv\Scripts\python.exe reader.py       # 抖音还需另装 douyinLive（见下文）
```

只想做抖音、不想再挂一个仓库？也可以按下面三步，用公开的上游项目 + 本仓库自带的转发器：

---

抖音的弹幕**不能直接从网页读**（要签名），社区通行做法是先跑一个**本地采集服务**，
再用本仓库自带的转发器把消息灌进桥。

#### 抖音三步

1. **拿采集服务**：开源项目 <https://github.com/jwwsjlm/douyinLive>（Go 写的，自带 ws + http）。
   自行编译或下载 release，改它目录下的 `config.yaml`（端口默认 `1089`、填抖音 cookie），启动。
2. **确认在跑**：

   ```powershell
   curl.exe "http://127.0.0.1:1089/api/v1/rooms/<房间号>/status"
   ```

3. **起转发器**（本仓库自带，`tools/douyin_relay.py`，零额外依赖）：

   ```powershell
   .venv\Scripts\python.exe tools\douyin_relay.py --room <房间号> --verbose
   ```

   它会连 `ws://127.0.0.1:1089/ws/<房间号>`，把**弹幕**和**礼物**翻译成
   `POST http://127.0.0.1:8795/api/danmaku`。
   通了之后，舞台页右侧「字幕 / 事件」里会出现 `【弹幕】` 条目。

> 转发器只做"翻译 + 转发"，不依赖采集器的内部实现 —— 换成别的采集器，只要它发同样的
> JSON（`method` / `user.nickname` / `content` / `gift`）也能用。
> ⚠️ 第三方采集工具与平台的合规风险由使用者自负；本项目只提供 `/api/danmaku` 这一个接口。

#### 其它平台 / 自己写采集器

只要按这个格式发请求，桥就认：

```http
POST http://127.0.0.1:8795/api/danmaku
Content-Type: application/json

{"nick":"观众名","content":"弹幕内容","platform":"bilibili","text":"念出来的文本"}
```

送礼事件额外带 `kind:"gift"`、`gift_item`、`gift_num`、`gift_value`（折算钻）。

### 2.6（可选）点播歌单

把 mp3/flac/wav 丢进 `audio/` 目录，舞台页「🎵 点播歌单」就能看到。
想要逐行歌词字幕，需要 `lyrics-cache/<歌名>.lrc.json`（用 `tools/lyrics_align.py` 生成，需要 ASR 环境）。
歌**不要提交进仓库**（`.gitignore` 已排除，版权也不允许）。

---

## 3. 配置 `config.json`

```powershell
copy config.example.json config.json
```

| 字段 | 填什么 |
|---|---|
| `vidu.api_key` | 你的 `vda_...` |
| `avatar.avatar_id` | 你上传的形象 ID（有 `image_uri` 就用那个） |
| `action.library_id` | 动作库 ID；不建就填 `"0"` |
| `rtc.mode` | `managed`（平台托管，推荐）或 `customer`（自备 RTC，要填 `rtc.artc.*`） |
| `llm.key_file` | 存 key 的文本文件路径 |
| `llm.system_prompt` | **你自己的人设**（模板里是示例，务必改） |
| `tts.omnivoice_base` | OmniVoice 地址，默认 `http://127.0.0.1:9877` |
| `tts.voices_dir` | 音色目录 |
| `tts.files_dir` | 点播目录，默认 `audio` |
| `bridge.port` | 默认 8795 |

`config.json` 里有密钥，**已被 `.gitignore` 排除**，不要提交。

---

## 4. 启动

```powershell
# 只起桥 + 舞台页（最简单）
.venv\Scripts\python.exe -m src.main

# 或者一键脚本：桥 + TTS + 弹幕 + 打开舞台页（缺的组件自动跳过）
双击 启动-组件版全链路.cmd
```

打开 <http://127.0.0.1:8795/stage>，点「开始连线」，等 5–15 秒画面出来。

> ⚠️ 连线即开始计费（1 积分/秒）。测完记得点「断开」。

---

## 5. 舞台页能干什么

| 区域 | 功能 |
|---|---|
| 中间 | 数字人画面 + 字幕 + 动作指令特效（只显示弹幕抓出来的指令） |
| 底部输入框 | 打字跟她聊（走 LLM → TTS → 说话） |
| 🎬 直发 | 直接把动作指令发给 Vidu，不经过 LLM（她默默执行） |
| 🕹 快捷指令 | 点一下即发送；编辑模式可拖拽排序、改名、新建 |
| 🎵 点播歌单 | 放歌（带歌词字幕） |
| 🖼 参考图 | 换装 / 拿起商品 / 换背景 |
| ⏺ 自动录播 | 让 Vidu 服务端录下这一场，播完自动下载到本地 |
| ⚙ 设置 | 音色、开场白、字幕位置、黑名单词表等 |

> 📌 **快捷指令组只带了示例**：🍉吃喝 14 条 / 💇外表 11 条 / 🎭拟人化 10 条 / 🎁拿出 8 条。
> 拟人化那 10 条是随机留的样例，真正的动作库请你在舞台页「🕹 快捷指令 → ✏️ 编辑」里自己加
> （支持拖拽排序、双击改名、跨组移动、⇩导出/⇧导入）。

---

## 6. 常见问题

**Q：连不上 Vidu / 401？**
检查 `vidu.api_key` 是否正确、余额是否 <45 积分（会直接开不了场）。

**Q：她没有声音？**
99% 是 TTS 没起来。先 `curl http://127.0.0.1:9877/` 看是不是 200；WSL2 重启后需要重新拉起服务。

**Q：WSL2 重启后连不上 9877？**
IP 变了。`wsl hostname -I` 查新 IP，改 `tts.omnivoice_base`，或者用镜像网络模式走 `127.0.0.1`。

**Q：画面卡 / 说话延迟大？**
先看 GPU 占用；TTS 和渲染抢显存时，把 OmniVoice 的 `--graph-buckets` 减少一些。

**Q：录播下载不到文件？**
Vidu 侧封盘可能要几分钟到几十分钟；页面「↻ 拉取录播」可以手动重试。

**Q：能换别的 TTS 吗？**
代码里 `tts.engine` 目前只实现 `omnivoice`；要接 Edge-TTS / GPT-SoVITS 需要自己写一个适配层（`src/tts/` 下加一个类即可）。

---

## 7. 仓库里**没有**什么

为了避免"下载后发现跑不起来"，这里明确列出作者**故意没放**的东西：

- ❌ 人物形象（图片/视频/形象模型）—— 需要你自己上传到 Vidu
- ❌ 克隆音色（参考音频、音色模型）
- ❌ 人设提示词正文、文案、歌单、动作库内容
- ❌ 任何 API Key、Cookie、账号凭据
- ❌ OmniVoice 模型权重（几 GB）、Python 依赖环境（2 GB+）、歌库音频
- ❌ 弹幕采集器（另一个项目，见 §2.5）

---
## 8. 依赖项
- 第三方依赖见 `requirements.txt`
