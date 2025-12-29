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

 Date: 30/12/2025 02:36:55
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
  `supplement_orders` int NOT NULL DEFAULT 0 COMMENT '补单数',
  `total_cost_diff` decimal(20, 8) NOT NULL DEFAULT 0.00000000 COMMENT '总损耗',
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
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of tasks
-- ----------------------------
INSERT INTO `tasks` VALUES (3, '李sir', '', '{}', 'error', 20156, '2025-12-29 17:20:54', '2025-12-29 17:14:25', 0, 0, 0, 0, 0.00000000, '策略执行异常: [Errno 22] Invalid argument', '2025-12-29 08:51:27', '2025-12-29 17:32:42', 1, 1, 1, 'SENTISUSDT', 600.00000000, 1, 50, 1, 'both', 'market');
INSERT INTO `tasks` VALUES (4, '立安', '', '{}', 'stopped', NULL, '2025-12-29 17:51:09', '2025-12-29 18:20:03', 0, 0, 0, 0, 0.00000000, NULL, '2025-12-29 11:55:38', '2025-12-29 18:20:03', 1, 6, 1, 'SENTISUSDT', 5000.00000000, 1, 50, 1, 'both', 'market');

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '邮箱',
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nickname` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '用户' COMMENT '昵称',
  `max_tasks` int NOT NULL DEFAULT 5 COMMENT '可创建任务数',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
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
INSERT INTO `users` VALUES (1, 'admin', 'admin@example.com', 'pbkdf2:sha256:260000$lLm6SzSz1XtCCnHW$26720140a2fe5b28cc1b2db437fce259516d07545faea68f61e953f0bc00f1e9', 'admin', 5, 1, 1, '2025-12-27 17:33:19', '2025-12-29 11:46:48');

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
) ENGINE = InnoDB AUTO_INCREMENT = 8 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of wallets
-- ----------------------------
INSERT INTO `wallets` VALUES (1, '李sir', '现货交易API', 'spot', 'gAAAAABpUhwOK7PcX6M7Di6t7j_PKw8E8DjtY08U4vmSwwkYln9CWMdZz2BGexYCRiGd9xynScvO9hovIsZy0MFCC6YAx0EYkEtOlDy5_GruOmpK20yoOkzFIDHpxvX9bTO6ldcav-xJrdHLpq4NB0Nf5Kn6crZM-H0DbAH3-s-ZvUmrHLQF0A0=', 'gAAAAABpUhwOgVkXfWPENgihSCvHt_g7slVNeEGAy5Fp_kpAy9OfHUa33-M7bsAuKg_9apj5EOYyumIGFnu8V1BqiDMuBuVzoJ1Vc_JiwLu55643iCxPocHapUt2R_XflaGYsgxGXuSz0xtyOHF98IftEFWcM1jR6jMYtdaFz90y2WLW6od3jyo=', NULL, NULL, NULL, 1, '2025-12-28 01:45:30', '2025-12-29 07:56:09', '2025-12-28 02:31:59', 1);
INSERT INTO `wallets` VALUES (2, '李sir', '期货交易API', 'futures', NULL, NULL, '0x056b241835dBe6F401BA19e94cB2039330445F33', '0x4273a4a866cf2f5ed8ab6dfd19a24f75eed43245', 'gAAAAABpUhwOKEVKlJMtCwSEnnW52iBASsu2M1KuuQzSgmf2109CUAgJbvnFMx7ecFVNUp4Qo9lD6xLSHgVmzewGj3W62ee_K8NxRDGk01lrTagA4V5puCAbSxCHc3Gm5jBHV0Yyc7AI-W8DfQkwjx7RuCcstLfMT4AA5IRouMzHwum4DUtLKNo=', 1, '2025-12-28 01:45:30', '2025-12-29 07:56:12', '2025-12-28 02:32:17', 1);
INSERT INTO `wallets` VALUES (4, '李sir_钱包2', '', 'spot', 'gAAAAABpUj-Hbwo_9BCwWZXDYjfJLuW6mo-fGbUQ01TB4nobFdVTGcMEIM23FS8rGwM-HEi6nNIV-rgx1v8o10J4U1tMXub99O9vjclviZPx4-QKVChMdTNSHMGaO3cX2LRlxVjmCtwnwpXwwgPKZPNYwGg8qUVQBAQQZzufHgKBrEkOnuVRujY=', 'gAAAAABpUj-HgVA4mRzHEdxIwaXh-g1wDOxap_iYWmYJJN70vatbdUxfs5LWfSWyeSLXfZ1iqCCojVFF2QojErOp3m2aw6-nhEQHABZKIHK7AYxrXMAcEAo8PNsQjH_ZXOvzdq4z2RzmeTLA6RmwvurZiV3J3QcKNfiDBDrbCX322nIq3Ar4tGQ=', '', '', NULL, 1, '2025-12-29 08:44:56', '2025-12-29 08:45:02', '2025-12-29 08:45:02', 1);
INSERT INTO `wallets` VALUES (5, '李sir_钱包2', '合约', 'futures', NULL, NULL, '0xd0e74bb1bde3d9bd8ce6ee03c4fb43af84ef7e2a', '0xd63616deeA748A3ea1cf163926e8B3eF7C92eCE8', 'gAAAAABpUj_qJ3snvnIjXQofjcDTxhdzVrWC3g_SvrazPVQU0eM7shTVfzy4FtHrSd2cu9KJmvBhmPOwfiMyuwBAAmnFEs9luDzSboyKxcwkM8VIR5qsGRCnJq6MCEEoRS-4yRz7zVtJvlodVL3d2wgkD6lZWJ4NXcF1fQVSoveM-uAuSop2Ehk=', 1, '2025-12-29 08:46:34', '2025-12-29 08:47:00', '2025-12-29 08:47:00', 1);
INSERT INTO `wallets` VALUES (6, '立安', '', 'spot', 'gAAAAABpUmpjHnnPzb1KPyeG7ITHU1dW-qSce6EMrbpy-O2FgbDuaboT5veKLF-JPqadZIfaC4PUPIpwUYyTr6mqi5AFMn7Ei10O-3w_Aak-nC7jgfJVI0G13hg94-8Jx453bXr0CkkoWdxEavF9Zcu_ug9GuiL9-7TMQ1gRvINSlc4TtO178j4=', 'gAAAAABpUmpj_42x_8tx4oOjleMRazn_E4ScRKQ1PsnLu9kfOAcagPwIgb3Qo1g47KytLWhGJvhalQH_zDVPlRZpnxi_YAEQ74BNsT_RC7AcFBHQfOv_0GCMjhGLbVrnp7P1f9swdKy-FBgtwIjDjePHDyCaoaGDnHy0INcCSQC-ICQbrkZTVms=', '', '', NULL, 1, '2025-12-29 11:47:47', '2025-12-29 11:47:50', '2025-12-29 11:47:50', 1);
INSERT INTO `wallets` VALUES (7, '立安', '', 'futures', NULL, NULL, '0xc7ca6ff4765fe8a3f8609fa677ad2ccc5d84b3e0', '0x87a56C656B35fDF400A0bD2Ef767008AFD95Ff9D', 'gAAAAABpUmqKvxFR7WsohmJZuYd6-rCCfvVouGGJKOTZmkB9ZkBKy15MGesjS0tjIcz8cFe-pH3lT5tKIf9zBf0YgeX_eABH_l4GzcRDPDtRnhiUGJepJbkBx4zkVOK22f-m5THDrJ4BAGeIPHZl7QB6n1lP-3u3iz_qEDXI5Dm9c-MJ7mzLJdQ=', 1, '2025-12-29 11:48:27', '2025-12-29 11:48:29', '2025-12-29 11:48:29', 1);

SET FOREIGN_KEY_CHECKS = 1;
