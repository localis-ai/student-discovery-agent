# Commit log

## 2026-11-18 — TBD — fix(sessions): make major selection work after completion and project it after commit
- **Chức năng chính:** `select_majors` được nhận khi activity đã hoàn thành; profile chỉ ghi sau khi commit; giới hạn 3 ngành (DEC-26).
- **Hàm/file quan trọng:** `sessions/services/turn_store.py::_snapshot`, `sessions/services/turns.py::_record_selection`, `sessions/services/turn_response.py::finalize_turn`, `workflow/ports.py::rank_career_groups`
- **Lưu ý khi debug:** Production chưa có ProfilePort bền vững (`TurnService.profile=None`); lựa chọn được lưu ở `StoredInteraction.major_ids`. Graph thấy xếp hạng qua `profile_overlay` trong scope, không qua profile.
