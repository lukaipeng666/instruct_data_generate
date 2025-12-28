package utils

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// JWTClaims JWT声明
type JWTClaims struct {
	UserID   uint   `json:"user_id"`
	Username string `json:"username"`
	IsAdmin  bool   `json:"is_admin"`
	jwt.RegisteredClaims
}

// JWTManager JWT管理器
type JWTManager struct {
	secretKey  []byte
	algorithm  jwt.SigningMethod
	expireTime time.Duration
}

// NewJWTManager 创建JWT管理器
func NewJWTManager(secretKey string, algorithm string, expireTime time.Duration) *JWTManager {
	return &JWTManager{
		secretKey:  []byte(secretKey),
		algorithm:  jwt.GetSigningMethod(algorithm),
		expireTime: expireTime,
	}
}

// GenerateToken 生成Token
func (j *JWTManager) GenerateToken(userID uint, username string, isAdmin bool) (string, error) {
	now := time.Now()
	claims := JWTClaims{
		UserID:   userID,
		Username: username,
		IsAdmin:  isAdmin,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(now.Add(j.expireTime)),
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
		},
	}

	token := jwt.NewWithClaims(j.algorithm, claims)
	return token.SignedString(j.secretKey)
}

// ValidateToken 验证Token
func (j *JWTManager) ValidateToken(tokenString string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
		if token.Method != j.algorithm {
			return nil, errors.New("无效的签名算法")
		}
		return j.secretKey, nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*JWTClaims); ok && token.Valid {
		return claims, nil
	}

	return nil, errors.New("无效的Token")
}
