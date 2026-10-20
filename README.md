# AgentChat

Môi trường để nhiều agent Claude trò chuyện và làm việc cùng nhau trong một
phòng chat, có giao diện web xem các agent trả lời theo thời gian thực.

## Cách hoạt động

```
Người dùng ──► Phòng chat (lịch sử chung) ──► Điều phối ──► Agent được chọn
                       ▲                                        │
                       └────────── câu trả lời (stream) ◄───────┘
```

- **Agent** (`agents.yaml`): mỗi agent có tên, vai trò (system prompt), model,
  mức `effort` và màu hiển thị.
- **Phòng chat** (`agentchat/room.py`): giữ lịch sử chung. Mỗi agent đọc toàn
  bộ lịch sử trước khi trả lời.
- **Điều phối**, có hai chế độ:
  - `moderator`: một model đọc hội thoại và chọn agent phù hợp nói tiếp
    (dùng structured output nên luôn trả về đúng tên agent).
  - `round_robin`: các agent nói lần lượt theo thứ tự trong file cấu hình.
- **Dừng** khi một agent viết `[DONE]`, khi đạt số lượt tối đa, hoặc khi bạn
  bấm **Dừng**. Bạn có thể chen tin nhắn vào bất cứ lúc nào; các agent sẽ đọc
  ở lượt tiếp theo.
- **Giao diện web** (`static/`): FastAPI + WebSocket, chữ hiện dần theo từng
  token.

## Cài đặt

Cần Python 3.10 trở lên.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-... # hoặc đăng nhập bằng `ant auth login`
python -m agentchat                 # mở http://127.0.0.1:8000
```

Muốn thử giao diện mà không gọi API (không tốn token):

```bash
AGENTCHAT_MOCK=1 python -m agentchat
```

Các tùy chọn khác: `--host 0.0.0.0`, `--port 8080`, `--reload`. Dùng file cấu
hình khác bằng `AGENTCHAT_CONFIG=duong/dan/agents.yaml`.

## Thêm hoặc sửa agent

Sửa `agents.yaml` rồi khởi động lại server:

```yaml
agents:
  - name: Tester
    color: "#ef4444"
    model: claude-opus-5-5       # hoặc claude-sonnet-5-5, claude-haiku-5-5
    effort: low                  # low | medium | high | xhigh | max
    system: |
      Bạn là Tester. Bạn viết unit test cho code của Coder.
```

Dòng đầu tiên của `system` được hiển thị làm mô tả vai trò ở thanh bên.

## Ghi chú kỹ thuật

- Mọi lời gọi model dùng Anthropic SDK chính thức (`anthropic`), stream câu
  trả lời và bật adaptive thinking.
- Với các model hỗ trợ (`claude-opus-5-5`, `claude-sonnet-5-5`, …), code bật
  `fallbacks: "default"`: nếu model từ chối một yêu cầu vì chính sách an toàn,
  API tự chạy lại trên model dự phòng. Muốn tắt thì xóa `_fallback_kwargs`
  trong `agentchat/llm.py`.
- Phòng chat chỉ nằm trong bộ nhớ; khởi động lại server là mất lịch sử. Mọi tab
  trình duyệt mở cùng lúc đều thấy chung một phòng.

## Chạy test

```bash
pip install pytest
pytest -q
```

Test dùng backend giả lập nên không cần API key.

## Hướng mở rộng

- Cho agent dùng tool (đọc/ghi file, chạy code) qua tool use của Claude API.
- Lưu lịch sử vào SQLite, hỗ trợ nhiều phòng.
- Sửa danh sách agent ngay trên giao diện.
