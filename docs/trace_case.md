# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case đã phân tích

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run `E-seeded_regression-20261117-9abc` |
| Triệu chứng | `pass_rate`, `refund_amount_correct`, `db_fact_kept` fail; reply nói đã hoàn 20.000đ, ledger ghi 20.000đ trong khi nhãn yêu cầu 0đ và status `denied`. |
| Bước sai đầu tiên | Event 3, `model_override {"delay_days": 5}`. |
| Vì sao là bước *đầu tiên* | Event 1 handoff đúng scope; event 2 investigator đã đọc đúng order `O-202` với `delay_days=2`; sai lệch chỉ xuất hiện khi ticket ghi “5 ngày” đè DB ở event 3. |
| Failure mode | FM-03 `ticket_trust`. |
| Đối chứng | `fixed C-002@11` không có `model_override`; event 3 là quote 0đ `no_entitlement`, event 4 reply từ chối, ledger 0đ và Lab 8 grader PASS. |
| Regression test | `tests/test_lab9_graders.py::test_override_event_breaks_db_fact` bắt event override; eval v1 bắt variant lỗi và `fixed` đạt 1.0 ở `db_fact_kept`, `refund_amount_correct`, `pass_rate`. |
| Chưa chắc chắn | Trace replay chỉ chứng minh lỗi trên MockLLM và fixture công khai; chưa suy rộng được tần suất trên model/dữ liệu thật. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
