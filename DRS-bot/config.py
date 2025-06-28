import jwt
API_BASE_URL = "http://localhost:5296"  
BOT_TOKEN = "8069174834:AAEc9u03IfYATsxpMKog1udMCEE4CI7ZRqs"
SIGNALR_HUB_URL = f"{API_BASE_URL}/notification/hub"

JWT_SECRET = "2fb69b1369027fe4fbe2ee4bdf10509c7f24eae866d6927d4e52ed992f24199f42e1b6c5c8fc014aeb4d3517486872aecac6b6d5bd3c5a182444e6f24bb2baf41ac7208bb7ba7c9c3878e39d7f7dfd8ce5a088ecb01c127af41def1d19f1259559abc57d573df8c272f3958b4208b07a69a74a7b4df6ec16cb68c2ffedf3e72859ce62fdb52e49a68adab6431758f05b1bd47eb7d751d353a126bc2952141f3bcf8e2e592c496e74a23aa5ee2dba9ad4350d7dec9dfcedc88b4dfebd0ed0646897f4fdf9bb3354f9187a1677c707e2dc586e377ff6767491bc9fff2cb695e8568234440766c058902df44572adf4588203f2783f7752aaba7da4fd15cc462e13"
JWT_ALGORITHM = "HS256"

def get_user_id_from_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token.replace("Bearer ", ""),
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        return payload['sub']
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
