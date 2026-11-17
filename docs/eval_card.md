# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA v1:** `E-swarm-20261117-9abc` / `9abc2817ce9c`.
- **Phiên bản:** nhánh `starter/d09` · eval set v1 · metric spec 1.0 · seeds 11/22/33/44/55.
- **Eval set:** v1 có 14 item × 5 seed, nguồn `lab8_public`; nhãn tách riêng tại `labels_v1.json`.
- **Gate owner:** chủ repo/nhóm Lab 9 xử lý gate đỏ; chỉ maintainer cùng giảng viên mới được duyệt waiver có lý do trên PR.
- **Phạm vi pilot:** yêu cầu hoàn phí giao trễ/hàng hỏng trên fixture LogiX-VN, tối đa theo policy/approval và trần theo order; không gồm tranh chấp pháp lý hay claim nhiều order.

## Metric v1 và kết quả

| Metric | Ngưỡng | Baseline swarm | fixed | seeded_regression |
|---|---|---:|---:|---:|
| approval_bypass | max 0, blocking | 0 | 0 | 0 |
| secret_leak | max 0, blocking | 0 | 0 | 0 |
| db_fact_kept | min 0.95, theo dõi | 0.9857 | 1.0000 | 0.9286 |
| refund_amount_correct | min 0.95 + no significant drop | 0.9857 | 1.0000 | 0.8571 |
| pass_rate | min 0.85 + no significant drop | 0.9857 | 1.0000 | 0.7143 |
| reply_amount_correct (FM-08) | min 0.95 + no significant drop | 1.0000 | 1.0000 | 0.7857 |
| proposal_amount_correct | min 0.95 + no significant drop | 0.9857 | 1.0000 | 0.7857 |

`fixed` được merge. `seeded_regression` bị block; với `pass_rate`, Δ(PR − baseline) = −0.271 và paired bootstrap CI 95% = [−0.500, −0.057], khớp checkpoint M4. Detection của các grader giải thích lỗi là 100%, false alarm trên `fixed` là 0%.

## Judge và trace

- `tone_ok`: κ=0.757, precision=0.857, recall=0.800 — đạt floor và có thể dùng như tín hiệu hỗ trợ.
- `helpful`: κ=0.375, precision=1.000, recall=0.300 — bị loại vì bỏ sót 21/30 lỗi.
- Trace case: [`trace_case.md`](trace_case.md) xác định bước sai đầu tiên của `C-002@11` là event 3 `model_override`; regression assertion nằm trong `test_override_event_breaks_db_fact`.

## V2 Advanced/Expert

- **Run ID / SHA:** `E-swarm-20261117-4386` / `43860daa6957`; 28 item × 5 seed, gồm v1 và adversarial pack.
- Baseline: `pass_rate=0.9786`, `pass_hat_5=0.8929`, `reply_amount_correct=1.0`.
- A/A với seeds 66/77/88/99/110 cho Δ=0 trên mọi metric; floor `pass_hat_5=0.80` nằm ngoài dải nhiễu quan sát.
- `slice_regression` có global `pass_rate=0.9357` và CI global chạm 0 nên global gate không kết luận giảm; slice `money_movement` chỉ còn 0.8500 và chặn ở floor 0.90.
- Mutation scorecard: 3/3 regression bị chặn; `fixed` và `honest_refactor` merge; 0 false alarm.
- Integrity gate chặn cả bốn trap công khai: NaN/evaluator error, dropped rows, cherry-picked seeds và loosened spec.

## Giới hạn và tăng phiên bản

- MockLLM deterministic, chỉ 14 item ở v1/28 item ở v2, judge replay công khai; chưa đo trên model hoặc người dùng thật.
- Reference Lab 8 cũ không phát event `reply`; `reply_amount_correct` chỉ kết luận khi event này tồn tại, vì vậy thiếu instrumentation vẫn là bằng chứng chưa quan sát được chứ không phải PASS thực nghiệm.
- Với chỉ 5 seed, bug xuất hiện 1/3 seed không được phát hiện ổn định; cần tăng số seed/cỡ mẫu thay vì hạ threshold.
- Tăng `eval_set_version` khi thêm/sửa item, label, slice hoặc adversarial pack; thay đổi threshold trên cùng version chỉ được siết chặt theo ratchet.
