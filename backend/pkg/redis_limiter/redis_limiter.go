package redis_limiter

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/go-redis/redis/v8"
)

// RedisLimiter 基于Redis的并发限制器
type RedisLimiter struct {
	client        *redis.Client
	maxConcurrent int
	keyPrefix     string
	ttl           time.Duration
}

// NewRedisLimiter 创建基于Redis的并发限制器
func NewRedisLimiter(client *redis.Client, maxConcurrent int, keyPrefix string, ttl time.Duration) *RedisLimiter {
	return &RedisLimiter{
		client:        client,
		maxConcurrent: maxConcurrent,
		keyPrefix:     keyPrefix,
		ttl:           ttl,
	}
}

// Acquire 获取并发槽位
func (rl *RedisLimiter) Acquire(ctx context.Context, key string) error {
	redisKey := rl.keyPrefix + key

	// 使用Lua脚本确保原子性操作
	// 脚本逻辑：
	// 1. 获取当前值
	// 2. 如果当前值小于最大并发数，则增加1并设置过期时间，返回新值
	// 3. 否则返回当前值
	script := redis.NewScript(
		`local current = redis.call('GET', KEYS[1])
		if current == false then
			current = 0
		else
			current = tonumber(current)
		end
		
		if current >= tonumber(ARGV[1]) then
			return current + 1  -- 返回超过限制的值以表示失败
		end
		
		local newCount = redis.call('INCR', KEYS[1])
		redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
		return newCount`,
	)

	result, err := script.Run(ctx, rl.client, []string{redisKey}, rl.maxConcurrent, int(rl.ttl.Seconds())).Result()
	if err != nil {
		return fmt.Errorf("执行Lua脚本失败: %w", err)
	}

	newCount := int(result.(int64))
	log.Printf("[RedisLimiter] 模型: %s, 当前槽位数: %d, 最大槽位数: %d", key, newCount-1, rl.maxConcurrent)

	// 检查是否超过了限制
	if newCount > rl.maxConcurrent {
		log.Printf("[RedisLimiter] 模型: %s, 槽位已满, 当前: %d, 最大: %d", key, newCount-1, rl.maxConcurrent)
		return fmt.Errorf("并发限制已达到上限: %d", rl.maxConcurrent)
	}

	log.Printf("[RedisLimiter] 成功获取槽位, 模型: %s, 新槽位数: %d", key, newCount)
	return nil
}

// Release 释放并发槽位
func (rl *RedisLimiter) Release(ctx context.Context, key string) {
	redisKey := rl.keyPrefix + key

	// 使用Lua脚本确保原子性操作
	// 脚本逻辑：
	// 1. 减少计数
	// 2. 如果结果 <= 0，删除key；否则重新设置过期时间
	script := redis.NewScript(
		`local count = redis.call('DECR', KEYS[1])
		if tonumber(count) <= 0 then
			redis.call('DEL', KEYS[1])
			return 0
		else
			redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
			return count
		end`,
	)

	result, err := script.Run(ctx, rl.client, []string{redisKey}, int(rl.ttl.Seconds())).Result()
	if err != nil {
		log.Printf("[RedisLimiter] 执行Lua脚本失败: %v", err)
		return
	}

	finalCount := int(result.(int64))
	if finalCount <= 0 {
		log.Printf("[RedisLimiter] 释放槽位完成并清理key, 模型: %s", key)
	} else {
		log.Printf("[RedisLimiter] 成功释放槽位, 模型: %s, 剩余槽位数: %d", key, finalCount)
	}
}

// GetCurrent 获取当前并发数
func (rl *RedisLimiter) GetCurrent(ctx context.Context, key string) (int, error) {
	redisKey := rl.keyPrefix + key
	current, err := rl.client.Get(ctx, redisKey).Int()
	if err != nil && err != redis.Nil {
		return 0, fmt.Errorf("获取当前并发数失败: %w", err)
	}
	if err == redis.Nil {
		return 0, nil
	}
	return current, nil
}

// GetMaxConcurrent 获取最大并发数
func (rl *RedisLimiter) GetMaxConcurrent() int {
	return rl.maxConcurrent
}
