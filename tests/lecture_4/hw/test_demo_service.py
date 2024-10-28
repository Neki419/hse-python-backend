from datetime import datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from lecture_4.demo_service.api.main import create_app
from lecture_4.demo_service.api.utils import initialize
from lecture_4.demo_service.core.users import (
    UserInfo,
    UserRole,
    UserService,
    password_is_longer_than_8,
)

@pytest.fixture()
def test_client():
    app = create_app()
    user_service = UserService(password_validators=[password_is_longer_than_8])
    user_service.register(
        UserInfo(
            username="superuser",
            name="Super Admin",
            birthdate=datetime(2000, 1, 1),
            role=UserRole.ADMIN,
            password=SecretStr("supersecurepassword"),
        )
    )
    app.state.user_service = user_service
    return TestClient(app)


def register_user(client, **kwargs):
    return client.post("/user-register", json=kwargs)


@pytest.mark.parametrize(
    "username,name,birthdate,password,expected_status,expected_response",
    [
        (
            "student_user",
            "Alice",
            "1998-10-12",
            "123456789",
            HTTPStatus.OK,
            {
                "username": "student_user",
                "name": "Alice",
                "birthdate": "1998-10-12T00:00:00",
                "uid": 2,
                "role": "user",
            },
        ),
        (
            "invalid_user",
            "Bob",
            "1997-03-15",
            "short",
            HTTPStatus.BAD_REQUEST,
            None,
        ),
        (
            "duplicate_user",
            "Charlie",
            "1995-07-25",
            "anothersecurepassword",
            HTTPStatus.BAD_REQUEST,
            None,
        ),
    ],
)
def test_register_user(
    test_client, username, name, birthdate, password, expected_status, expected_response
):
    if expected_status == HTTPStatus.BAD_REQUEST and username == "duplicate_user":
        register_user(
            test_client,
            username="duplicate_user",
            name="Already Exists",
            birthdate="1994-04-22",
            password="longsecurepassword",
        )

    response = register_user(
        test_client,
        username=username,
        name=name,
        birthdate=birthdate,
        password=password,
    )
    assert response.status_code == expected_status
    if expected_response:
        assert response.json() == expected_response


@pytest.mark.parametrize(
    "params,auth,expected_status,expected_response",
    [
        (
            {"id": 3, "username": "student_user"},
            ("superuser", "supersecurepassword"),
            HTTPStatus.BAD_REQUEST,
            None,
        ),
        ({}, ("superuser", "supersecurepassword"), HTTPStatus.BAD_REQUEST, None),
        (
            {"id": 1},
            ("superuser", "supersecurepassword"),
            HTTPStatus.OK,
            {
                "uid": 1,
                "username": "superuser",
                "name": "Super Admin",
                "birthdate": "2000-01-01T00:00:00",
                "role": "admin",
            },
        ),
        (
            {"username": "superuser"},
            ("superuser", "supersecurepassword"),
            HTTPStatus.OK,
            {
                "uid": 1,
                "username": "superuser",
                "name": "Super Admin",
                "birthdate": "2000-01-01T00:00:00",
                "role": "admin",
            },
        ),
        ({"id": 1}, ("superuser", "wrongpassword"), HTTPStatus.UNAUTHORIZED, None),
        (
            {"username": "unknown_user"},
            ("superuser", "supersecurepassword"),
            HTTPStatus.NOT_FOUND,
            None,
        ),
    ],
)
def test_user_get(test_client, params, auth, expected_status, expected_response):
    response = test_client.post("/user-get", params=params, auth=auth)
    assert response.status_code == expected_status
    if expected_response:
        assert response.json() == expected_response

@pytest.mark.parametrize(
    "setup,params,auth,expected_status",
    [
        (None, {"id": 1}, ("superuser", "supersecurepassword"), HTTPStatus.OK),
        (None, {"id": 99}, ("superuser", "supersecurepassword"), HTTPStatus.BAD_REQUEST),
        (
            {
                "username": "limited_user",
                "name": "User Test",
                "birthdate": "1990-08-18",
                "password": "validpassword123",
            },
            {"id": 1},
            ("limited_user", "validpassword123"),
            HTTPStatus.FORBIDDEN,
        ),
    ],
)
def test_user_promote(test_client, setup, params, auth, expected_status):
    if setup:
        register_user(test_client, **setup)

    response = test_client.post("/user-promote", params=params, auth=auth)
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_initialize():
    app = create_app()
    
    # Инициализация приложения с корректной регистрацией пользователя
    async with initialize(app):
        user_service = app.state.user_service
        
        # Проверка наличия зарегистрированных пользователей
        admin = user_service.get_by_username("admin")  # Изменено на "admin"
        assert admin is not None, "User 'admin' was not found in user service."
        
        assert admin.uid == 1
        admin_info = admin.info
        assert admin_info.username == "admin"  # Изменено на "admin"
        assert admin_info.name == "admin"
        assert admin_info.birthdate == datetime.fromtimestamp(0.0)
        assert admin_info.role == UserRole.ADMIN
        assert admin_info.password == SecretStr("superSecretAdminPassword123")