# Capability Matrix

Source of truth for which transport mode supports which operation.
Keep in sync with `scripts/capabilities.py::CAPABILITIES`.

| Operation | `official` | `browser` | Preferred (auto) | Notes |
|-----------|:---------:|:---------:|:---------------:|-------|
| `get_user` | ✅ | ✅ | official | `/partner/users/me` vs `/api/v1/user/me/` |
| `get_categories` | ✅ | ✅ | official | Cached locally after first fetch |
| `create_advert` | ✅ | ✅ | official | API gated on approval |
| `edit_advert` | ✅ | ✅ | official | |
| `list_my_adverts` | ✅ | ✅ | official | |
| `delete_advert` | ✅ | ✅ | official | |
| `upload_photo` | ✅ | ✅ | official | Assumed present — verify at impl |
| `search_competitors` | — | ✅ | browser | Public search doesn't need partner API |
| `apply_promotion` | — | ✅ | browser | Paid promotions not in Partner API (assumed) |

Update this table whenever `CAPABILITIES` changes.
