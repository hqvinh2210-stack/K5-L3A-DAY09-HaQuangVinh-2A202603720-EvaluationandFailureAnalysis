# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Confusion (tp/fp/fn/tn) | Quyết định |
|---|---:|---:|---:|---:|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | Dùng: đạt cả ba floor |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9 / 0 / 21 / 70 | Loại: κ và recall không đạt |

Tone judge có fail rate quan sát 0.28 và Rogan–Gladen hiệu chỉnh thành 0.30. Helpful judge quan sát 0.09 nhưng bỏ sót 21/30 lỗi; precision 1.0 không bù được sự thiếu nhạy này.

## ≥5 case audit thủ công

| Case | Human / judge | Ai đúng | Hành động sửa rubric |
|---|---|---|---|
| H-008 | FAIL / PASS | Human: “anh/em” quá thân mật và thiếu chuẩn CSKH. | Thêm ví dụ âm cho đại từ suồng sã; không cho câu ngắn tự động PASS. |
| H-017 | FAIL / PASS | Human: “bạn ơi” là xưng hô không phù hợp. | Liệt kê rõ các cách gọi bị cấm (`bạn ơi`, `em/anh` không theo ngữ cảnh). |
| H-029 | FAIL / PASS | Human: mệnh lệnh “không cần nhắn thêm” thiếu tôn trọng. | Bổ sung tiêu chí không được đóng kênh hỗ trợ hoặc ra lệnh cho khách. |
| H-042 | PASS / FAIL | Human: câu lịch sự, rõ số tiền và thời gian. | Thêm ví dụ dương có ETA 3–5 ngày; không phạt số tiền/ETA trung tính. |
| H-051 | PASS / FAIL | Human: câu ngắn nhưng lịch sự và đầy đủ hành động. | Cho phép thuật ngữ “refund” nếu câu vẫn rõ và trung tính. |
| H-063 | FAIL / PASS | Human: hứa “sẽ hoàn thêm” mơ hồ, dễ gây hiểu sai. | Thêm rule chống cam kết tương lai không có căn cứ ledger/policy. |
| H-070 | FAIL / PASS | Human: emoji cười trong thông báo hoàn tiền là không chuyên nghiệp. | Thêm emoji chế giễu/cảm xúc quá mức vào ví dụ âm. |
| H-081 | PASS / FAIL | Human: từ chối lịch sự theo chính sách là tone hợp lệ. | Thêm ví dụ dương cho denial; không đồng nhất từ chối với tone xấu. |

## Kết luận
- Loại `helpful` khỏi gate: 21 false negative làm recall chỉ 0.300 và κ 0.375; judge gần như chỉ gắn FAIL cho trường hợp hiển nhiên.
- Giữ `tone_ok` như tín hiệu hỗ trợ vì đạt cả ba floor, nhưng tiền và approval vẫn do code grader xử lý.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
