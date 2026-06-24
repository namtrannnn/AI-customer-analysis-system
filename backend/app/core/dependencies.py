from fastapi import Depends, HTTPException, WebSocket, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.core.security import ALGORITHM, SECRET_KEY
from app.database.session import get_db
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _resolve_credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Khong the xac thuc thong tin dang nhap (token khong hop le hoac da het han).",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_username_from_token(token: str) -> str:
    credentials_exception = _resolve_credentials_exception()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")

        if username is None:
            raise credentials_exception

        return username
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc


def get_user_from_token(token: str, db: Session) -> User:
    username = _decode_username_from_token(token)
    credentials_exception = _resolve_credentials_exception()

    user = db.query(User).filter(User.username == username, User.status != "deleted").first()

    if user is None:
        raise credentials_exception

    if user.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tai khoan cua ban da bi khoa.",
        )

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    return get_user_from_token(token=token, db=db)


def user_has_permission(db: Session, user: User, required_permission: str) -> bool:
    user_role_record = db.query(UserRole).filter(UserRole.user_id == user.id).first()

    if not user_role_record:
        return False

    current_role_id = user_role_record.role_id
    user_role = db.query(Role).filter(Role.id == current_role_id).first()

    if user_role and user_role.role_code == "admin":
        return True

    has_permission = db.query(RolePermission).join(
        Permission, RolePermission.permission_id == Permission.id
    ).filter(
        RolePermission.role_id == current_role_id,
        Permission.permission_code == required_permission,
    ).first()

    return has_permission is not None


def ensure_user_has_permission(db: Session, user: User, required_permission: str) -> User:
    if not user_has_permission(db=db, user=user, required_permission=required_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Truy cap bi tu choi! Ban khong co quyen thuc hien hanh dong nay. (Ma: {required_permission})",
        )

    return user


def authenticate_websocket_user(
    websocket: WebSocket,
    db: Session,
    required_permission: str | None = None,
) -> User:
    token = websocket.query_params.get("token")

    if not token:
        authorization = websocket.headers.get("authorization")

        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()

    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Thieu token xac thuc cho WebSocket.",
        )

    try:
        user = get_user_from_token(token=token, db=db)
    except HTTPException as exc:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=str(exc.detail),
        ) from exc

    if required_permission and not user_has_permission(
        db=db,
        user=user,
        required_permission=required_permission,
    ):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Khong co quyen {required_permission}.",
        )

    return user


def get_admin_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    is_admin = db.query(UserRole).join(
        Role, UserRole.role_id == Role.id
    ).filter(
        UserRole.user_id == current_user.id,
        Role.role_code == "admin",
    ).first()

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cap bi tu choi. Chi Quan tri vien (Admin) moi co quyen thuc hien hanh dong nay.",
        )

    return current_user


class RequirePermission:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        has_role = db.query(UserRole).filter(UserRole.user_id == current_user.id).first()

        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tai khoan cua ban chua duoc phan quyen de su dung he thong.",
            )

        return ensure_user_has_permission(
            db=db,
            user=current_user,
            required_permission=self.required_permission,
        )
