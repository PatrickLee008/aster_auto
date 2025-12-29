/*
 Navicat Premium Dump SQL

 Source Server         : localhost_3306
 Source Server Type    : MySQL
 Source Server Version : 80043 (8.0.43)
 Source Host           : localhost:3306
 Source Schema         : aster_auto

 Target Server Type    : MySQL
 Target Server Version : 80043 (8.0.43)
 File Encoding         : 65001

 Date: 29/12/2025 14:24:07
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for strategies
-- ----------------------------
DROP TABLE IF EXISTS `strategies`;
CREATE TABLE `strategies`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `strategy_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `supported_wallet_types` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `module_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `class_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_parameters` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `is_active` tinyint(1) NULL DEFAULT NULL,
  `created_at` datetime NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of strategies
-- ----------------------------
INSERT INTO `strategies` VALUES (1, '现货刷量策略', '现货刷量交易策略，通过买卖相同数量和价格的现货来刷交易量', 'volume', 'spot', 'strategies.volume_strategy', 'VolumeStrategy', '{\"symbol\": \"SENTISUSDT\", \"quantity\": \"101.0\", \"interval\": 5, \"rounds\": 3}', 1, '2025-12-27 17:33:19');
INSERT INTO `strategies` VALUES (2, '合约HIDDEN自成交策略', '使用HIDDEN隐藏订单实现合约自成交，零风险策略', 'hidden_futures', 'futures', 'strategies.hidden_futures_strategy', 'HiddenFuturesStrategy', '{\"symbol\": \"SKYUSDT\", \"quantity\": \"3249.0\", \"leverage\": 20, \"rounds\": 5, \"interval\": 3}', 1, '2025-12-27 17:33:19');

-- ----------------------------
-- Table structure for tasks
-- ----------------------------
DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `strategy_parameters` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `process_id` int NULL DEFAULT NULL,
  `start_time` datetime NULL DEFAULT NULL,
  `end_time` datetime NULL DEFAULT NULL,
  `total_rounds` int NULL DEFAULT NULL,
  `successful_rounds` int NULL DEFAULT NULL,
  `failed_rounds` int NULL DEFAULT NULL,
  `last_error` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` datetime NULL DEFAULT NULL,
  `updated_at` datetime NULL DEFAULT NULL,
  `user_id` int NOT NULL,
  `wallet_id` int NOT NULL,
  `strategy_id` int NOT NULL,
  `symbol` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BTCUSDT',
  `quantity` decimal(20, 8) NOT NULL DEFAULT 1.00000000,
  `interval` int NOT NULL DEFAULT 60,
  `rounds` int NOT NULL DEFAULT 1,
  `leverage` int NULL DEFAULT 1,
  `side` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'buy',
  `order_type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'market',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  INDEX `wallet_id`(`wallet_id` ASC) USING BTREE,
  INDEX `strategy_id`(`strategy_id` ASC) USING BTREE,
  CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_2` FOREIGN KEY (`wallet_id`) REFERENCES `wallets` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_3` FOREIGN KEY (`strategy_id`) REFERENCES `strategies` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of tasks
-- ----------------------------
INSERT INTO `tasks` VALUES (1, '测试', '测试', '{}', 'stopped', NULL, '2025-12-29 06:19:06', '2025-12-29 06:20:37', 0, 0, 0, NULL, '2025-12-28 02:34:14', '2025-12-29 06:20:37', 1, 2, 2, 'SKYUSDT', 3000.00000000, 5, 3, 20, 'both', 'market');
INSERT INTO `tasks` VALUES (2, '测试', '测试', '{}', 'stopped', NULL, '2025-12-29 06:08:03', '2025-12-29 06:10:06', 0, 0, 0, NULL, '2025-12-29 01:58:15', '2025-12-29 06:10:06', 1, 1, 1, 'SENTISUSDT', 101.00000000, 5, 3, 1, 'buy', 'market');

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_admin` tinyint(1) NULL DEFAULT NULL,
  `created_at` datetime NULL DEFAULT NULL,
  `last_login` datetime NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `username`(`username` ASC) USING BTREE,
  UNIQUE INDEX `email`(`email` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO `users` VALUES (1, 'admin', 'admin@example.com', 'pbkdf2:sha256:260000$lLm6SzSz1XtCCnHW$26720140a2fe5b28cc1b2db437fce259516d07545faea68f61e953f0bc00f1e9', 1, '2025-12-27 17:33:19', '2025-12-29 06:08:01');

-- ----------------------------
-- Table structure for wallets
-- ----------------------------
DROP TABLE IF EXISTS `wallets`;
CREATE TABLE `wallets`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `wallet_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `api_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `secret_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `user_address` varchar(42) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `signer_address` varchar(42) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `private_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `is_active` tinyint(1) NULL DEFAULT NULL,
  `created_at` datetime NULL DEFAULT NULL,
  `updated_at` datetime NULL DEFAULT NULL,
  `last_used` datetime NULL DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  CONSTRAINT `wallets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of wallets
-- ----------------------------
INSERT INTO `wallets` VALUES (1, '我自己的钱包', '现货交易API', 'spot', 'gAAAAABpUhwOK7PcX6M7Di6t7j_PKw8E8DjtY08U4vmSwwkYln9CWMdZz2BGexYCRiGd9xynScvO9hovIsZy0MFCC6YAx0EYkEtOlDy5_GruOmpK20yoOkzFIDHpxvX9bTO6ldcav-xJrdHLpq4NB0Nf5Kn6crZM-H0DbAH3-s-ZvUmrHLQF0A0=', 'gAAAAABpUhwOgVkXfWPENgihSCvHt_g7slVNeEGAy5Fp_kpAy9OfHUa33-M7bsAuKg_9apj5EOYyumIGFnu8V1BqiDMuBuVzoJ1Vc_JiwLu55643iCxPocHapUt2R_XflaGYsgxGXuSz0xtyOHF98IftEFWcM1jR6jMYtdaFz90y2WLW6od3jyo=', NULL, NULL, NULL, 1, '2025-12-28 01:45:30', '2025-12-29 06:13:35', '2025-12-28 02:31:59', 1);
INSERT INTO `wallets` VALUES (2, '我自己的钱包', '期货交易API', 'futures', NULL, NULL, '0x056b241835dBe6F401BA19e94cB2039330445F33', '0x4273a4a866cf2f5ed8ab6dfd19a24f75eed43245', 'gAAAAABpUhwOKEVKlJMtCwSEnnW52iBASsu2M1KuuQzSgmf2109CUAgJbvnFMx7ecFVNUp4Qo9lD6xLSHgVmzewGj3W62ee_K8NxRDGk01lrTagA4V5puCAbSxCHc3Gm5jBHV0Yyc7AI-W8DfQkwjx7RuCcstLfMT4AA5IRouMzHwum4DUtLKNo=', 1, '2025-12-28 01:45:30', '2025-12-29 06:13:35', '2025-12-28 02:32:17', 1);

SET FOREIGN_KEY_CHECKS = 1;
