# Ruleset cho các thành viên

`main-protection.json` là file import vào GitHub, bảo vệ nhánh mặc định (hiện là `main`). File có trạng thái `active`: các quy tắc có hiệu lực sau khi import và lưu trên GitHub. Chỉ thêm file vào repo không tự kích hoạt ruleset.

## Quy tắc

- Mọi thay đổi vào nhánh mặc định phải qua pull request.
- Cần ít nhất một approval từ người có quyền review phù hợp. Tác giả PR không tự duyệt PR của mình; người duyệt lần push cuối phải khác người push.
- Commit mới làm mất hiệu lực các approval trước đó.
- Phải giải quyết các thảo luận review trước khi merge.
- Chặn force push và xóa nhánh mặc định.
- Không có bypass, áp dụng cả admin. Admin có quyền quản lý ruleset vẫn có thể sửa hoặc tắt ruleset.

Nhóm cần ít nhất hai người có quyền phù hợp để duyệt và merge PR. Thành viên phát triển thường cần quyền Write; chỉ giao quyền Admin cho người quản lý repo.

## Import

1. Mở repo `localis-ai/student-discovery-agent` trên GitHub.
2. Vào **Settings → Rules → Rulesets**.
3. Chọn **New ruleset → Import a ruleset** và chọn `main-protection.json`.
4. Kiểm tra tên, trạng thái **Active**, nhánh **Default branch**, bypass và các quy tắc; lưu.
5. Thử bằng một PR nhỏ: phải có approval của người khác mới merge được. Không thử force push hoặc xóa nhánh chính để kiểm tra.

Nếu đã có ruleset bảo vệ nhánh mặc định, kiểm tra và cập nhật ruleset đó thay vì import trùng; nhiều ruleset có thể cùng áp dụng.

## CI và quyền truy cập

Chưa yêu cầu status checks vì lúc tạo file repo chưa có `.github/workflows`. Khi thêm CI, chờ workflow chạy thành công rồi bổ sung đúng tên check vào ruleset trên GitHub. Chưa bắt buộc CODEOWNERS hoặc commit signature vì chưa thiết lập các quy trình đó.

Ruleset quản lý nhánh, không cấp quyền cho thành viên và không chặn file theo đường dẫn. `.gitignore` cũng không chặn `git add -f`; việc kiểm soát file nhạy cảm cần cơ chế riêng nếu nhóm yêu cầu.

Khả năng sử dụng rulesets phụ thuộc visibility của repo và gói GitHub. Xem tài liệu chính thức nếu GitHub không cho kích hoạt.

Nguồn: [GitHub REST schema](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset) và [quản lý/import rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository).
