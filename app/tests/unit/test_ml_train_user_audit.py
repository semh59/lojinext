from unittest.mock import AsyncMock, MagicMock, patch


async def test_ml_train_passes_user_id_to_service():
    """
    Train endpoint, current_admin.id'yi servis çağrısına iletmeli.
    """
    from v2.modules.prediction_ml.api import predictions as pred_mod

    mock_admin = MagicMock()
    mock_admin.id = 42

    captured_kwargs = {}

    async def fake_train(arac_id, user_id=None):
        captured_kwargs["user_id"] = user_id
        return {"status": "success", "message": "eğitim başladı"}

    mock_service = MagicMock()
    mock_service.train_xgboost_model = fake_train

    with patch.object(pred_mod, "PredictionService", return_value=mock_service):
        await pred_mod.train_vehicle_model(
            arac_id=21,
            current_admin=mock_admin,
        )

    assert captured_kwargs.get("user_id") == 42, (
        f"user_id=42 beklendi, geldi: {captured_kwargs.get('user_id')}"
    )


async def test_create_user_uses_current_user_id():
    """admin_user_routes.py: olusturan_id = current_user.id olmalı."""
    from v2.modules.auth_rbac.api import admin_user_routes as au_mod

    mock_user = MagicMock()
    mock_user.id = 7

    captured = {}

    async def fake_create(data_dict, created_by_id):
        captured["created_by_id"] = created_by_id
        return {"id": 99, "email": "test@test.com"}

    with (
        patch.object(au_mod.user_service, "create_user", fake_create),
        patch.object(au_mod, "log_audit_event", new=AsyncMock()),
    ):
        fake_data = MagicMock()
        fake_data.model_dump.return_value = {
            "email": "test@test.com",
            "ad_soyad": "Test",
            "rol_id": 2,
            "sifre": "pass123",
        }
        fake_data.email = "test@test.com"
        fake_data.rol_id = 2
        await au_mod.create_user(data=fake_data, current_user=mock_user)

    assert captured.get("created_by_id") == 7, (
        f"created_by_id=7 beklendi, geldi: {captured.get('created_by_id')}"
    )
