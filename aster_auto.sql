-- MySQL dump 10.13  Distrib 8.0.36, for Linux (x86_64)
--
-- Host: localhost    Database: aster_auto
-- ------------------------------------------------------
-- Server version	8.0.36

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `strategies`
--

DROP TABLE IF EXISTS `strategies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `strategies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `strategy_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `supported_wallet_types` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `module_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `class_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_parameters` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `is_active` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `strategies`
--

LOCK TABLES `strategies` WRITE;
/*!40000 ALTER TABLE `strategies` DISABLE KEYS */;
INSERT INTO `strategies` VALUES (1,'现货刷量策略','现货刷量交易策略，通过买卖相同数量和价格的现货来刷交易量','volume','spot','strategies.volume_strategy','VolumeStrategy','{\"symbol\": \"SENTISUSDT\", \"quantity\": \"101.0\", \"interval\": 5, \"rounds\": 3}',1,'2025-12-27 17:33:19'),(2,'合约HIDDEN自成交策略','使用HIDDEN隐藏订单实现合约自成交，零风险策略','hidden_futures','futures','strategies.hidden_futures_strategy','HiddenFuturesStrategy','{\"symbol\": \"SKYUSDT\", \"quantity\": \"3249.0\", \"leverage\": 20, \"rounds\": 5, \"interval\": 3}',1,'2025-12-27 17:33:19');
/*!40000 ALTER TABLE `strategies` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tasks`
--

DROP TABLE IF EXISTS `tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `strategy_parameters` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `process_id` int DEFAULT NULL,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `total_rounds` int DEFAULT NULL,
  `successful_rounds` int DEFAULT NULL,
  `failed_rounds` int DEFAULT NULL,
  `supplement_orders` int NOT NULL DEFAULT '0' COMMENT '补单数',
  `total_cost_diff` decimal(20,8) NOT NULL DEFAULT '0.00000000' COMMENT '总损耗',
  `last_error` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `user_id` int NOT NULL,
  `wallet_id` int NOT NULL,
  `strategy_id` int NOT NULL,
  `symbol` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BTCUSDT',
  `quantity` decimal(20,8) NOT NULL DEFAULT '1.00000000',
  `interval` int NOT NULL DEFAULT '60',
  `rounds` int NOT NULL DEFAULT '1',
  `leverage` int DEFAULT '1',
  `side` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'buy',
  `order_type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'market',
  `buy_volume_usdt` decimal(20,8) DEFAULT '0.00000000' COMMENT '买单总交易量(USDT)',
  `sell_volume_usdt` decimal(20,8) DEFAULT '0.00000000' COMMENT '卖单总交易量(USDT)',
  `total_fees_usdt` decimal(20,8) DEFAULT '0.00000000' COMMENT '总手续费(USDT)',
  `initial_usdt_balance` decimal(20,8) DEFAULT '0.00000000' COMMENT '初始USDT余额',
  `final_usdt_balance` decimal(20,8) DEFAULT '0.00000000' COMMENT '最终USDT余额',
  `usdt_balance_diff` decimal(20,8) DEFAULT '0.00000000' COMMENT 'USDT余额差值',
  `net_loss_usdt` decimal(20,8) DEFAULT '0.00000000' COMMENT '净损耗(USDT)',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `user_id` (`user_id`) USING BTREE,
  KEY `wallet_id` (`wallet_id`) USING BTREE,
  KEY `strategy_id` (`strategy_id`) USING BTREE,
  CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_2` FOREIGN KEY (`wallet_id`) REFERENCES `wallets` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `tasks_ibfk_3` FOREIGN KEY (`strategy_id`) REFERENCES `strategies` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tasks`
--

LOCK TABLES `tasks` WRITE;
/*!40000 ALTER TABLE `tasks` DISABLE KEYS */;
INSERT INTO `tasks` VALUES (4,'立安','','{}','stopped',NULL,'2025-12-30 14:09:57','2025-12-30 14:51:58',446,446,0,161,10.04280736,NULL,'2025-12-29 11:55:38','2025-12-30 14:51:58',1,6,1,'SENTISUSDT',30000.00000000,1,700,1,'both','market',0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000),(6,'海伦_钱包01_lisa','','{}','stopped',NULL,'2025-12-30 13:49:24','2025-12-30 13:57:59',96,96,0,18,1.50294102,NULL,'2025-12-30 13:17:57','2025-12-30 13:57:59',1,10,1,'LISAUSDT',600.00000000,2,100,1,'both','market',0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000),(7,'Kenn_钱包02_lisa','','{}','stopped',NULL,'2025-12-30 14:13:28','2025-12-30 14:22:20',100,100,0,8,0.71002930,NULL,'2025-12-30 14:10:08','2025-12-30 14:22:20',1,11,1,'LISAUSDT',601.00000000,2,100,1,'both','market',0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000),(10,'李sir_GAIX','','{}','stopped',NULL,'2025-12-30 19:18:48','2025-12-30 19:20:03',10,10,0,0,0.00000000,NULL,'2025-12-30 18:47:15','2025-12-30 19:20:03',1,8,1,'GAIXUSDT',112.00000000,2,10,1,'both','market',108.20711000,118.31200000,0.01903001,3160.16258691,3170.25236312,10.08977621,10.07074620),(11,'立安','21','{}','stopped',NULL,NULL,NULL,0,0,0,0,0.00000000,NULL,'2025-12-30 19:32:50','2025-12-30 19:32:50',2,12,1,'21',21.00000000,1,1,1,'both','market',0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000,0.00000000);
/*!40000 ALTER TABLE `tasks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '邮箱',
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nickname` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '用户' COMMENT '昵称',
  `max_tasks` int NOT NULL DEFAULT '5' COMMENT '可创建任务数',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `is_admin` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `username` (`username`) USING BTREE,
  UNIQUE KEY `email` (`email`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'admin','admin@example.com','pbkdf2:sha256:260000$lLm6SzSz1XtCCnHW$26720140a2fe5b28cc1b2db437fce259516d07545faea68f61e953f0bc00f1e9','admin',100,1,1,'2025-12-27 17:33:19','2025-12-30 19:33:12'),(2,'lian',NULL,'pbkdf2:sha256:600000$XhxkfiRefn5NfJHN$f95812d0a855d405c120a54c962ca38bb3a87253c24e80126ead0637db68343f','立安',1,1,0,'2025-12-30 19:30:53','2025-12-30 19:35:24'),(3,'hailun',NULL,'pbkdf2:sha256:600000$mk2As468XGFJIuuQ$9a38dfccb0a2c1b41aaf0c6c98b37221833f3ae8d5d737869f44744a8f22db07','海伦',1,1,0,'2025-12-30 19:33:36',NULL),(4,'zongwei',NULL,'pbkdf2:sha256:600000$3bsIh5e5kkrrfSwJ$b282b7baeecae8d7a907499d9fd3922ae11cb8d63afa1d029b85145722e079e0','棕伟',1,1,0,'2025-12-30 19:33:51',NULL),(5,'zijian',NULL,'pbkdf2:sha256:600000$IVtf4sN30z3L0oGU$89ce7dc94fc90fe0fdfd25f215b4344517d3e3de953f66d9f73e52a4f0522583','子健',1,1,0,'2025-12-30 19:34:12',NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `wallets`
--

DROP TABLE IF EXISTS `wallets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wallets` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `wallet_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `api_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `secret_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `user_address` varchar(42) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `signer_address` varchar(42) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `private_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `is_active` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `last_used` datetime DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  KEY `user_id` (`user_id`) USING BTREE,
  CONSTRAINT `wallets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `wallets`
--

LOCK TABLES `wallets` WRITE;
/*!40000 ALTER TABLE `wallets` DISABLE KEYS */;
INSERT INTO `wallets` VALUES (1,'李sir','现货交易API','spot','gAAAAABpUhwOK7PcX6M7Di6t7j_PKw8E8DjtY08U4vmSwwkYln9CWMdZz2BGexYCRiGd9xynScvO9hovIsZy0MFCC6YAx0EYkEtOlDy5_GruOmpK20yoOkzFIDHpxvX9bTO6ldcav-xJrdHLpq4NB0Nf5Kn6crZM-H0DbAH3-s-ZvUmrHLQF0A0=','gAAAAABpUhwOgVkXfWPENgihSCvHt_g7slVNeEGAy5Fp_kpAy9OfHUa33-M7bsAuKg_9apj5EOYyumIGFnu8V1BqiDMuBuVzoJ1Vc_JiwLu55643iCxPocHapUt2R_XflaGYsgxGXuSz0xtyOHF98IftEFWcM1jR6jMYtdaFz90y2WLW6od3jyo=',NULL,NULL,NULL,1,'2025-12-28 01:45:30','2025-12-29 07:56:09','2025-12-28 02:31:59',1),(2,'李sir','期货交易API','futures',NULL,NULL,'0x056b241835dBe6F401BA19e94cB2039330445F33','0x4273a4a866cf2f5ed8ab6dfd19a24f75eed43245','gAAAAABpUhwOKEVKlJMtCwSEnnW52iBASsu2M1KuuQzSgmf2109CUAgJbvnFMx7ecFVNUp4Qo9lD6xLSHgVmzewGj3W62ee_K8NxRDGk01lrTagA4V5puCAbSxCHc3Gm5jBHV0Yyc7AI-W8DfQkwjx7RuCcstLfMT4AA5IRouMzHwum4DUtLKNo=',1,'2025-12-28 01:45:30','2025-12-29 07:56:12','2025-12-28 02:32:17',1),(4,'李sir_钱包2','','spot','gAAAAABpUj-Hbwo_9BCwWZXDYjfJLuW6mo-fGbUQ01TB4nobFdVTGcMEIM23FS8rGwM-HEi6nNIV-rgx1v8o10J4U1tMXub99O9vjclviZPx4-QKVChMdTNSHMGaO3cX2LRlxVjmCtwnwpXwwgPKZPNYwGg8qUVQBAQQZzufHgKBrEkOnuVRujY=','gAAAAABpUj-HgVA4mRzHEdxIwaXh-g1wDOxap_iYWmYJJN70vatbdUxfs5LWfSWyeSLXfZ1iqCCojVFF2QojErOp3m2aw6-nhEQHABZKIHK7AYxrXMAcEAo8PNsQjH_ZXOvzdq4z2RzmeTLA6RmwvurZiV3J3QcKNfiDBDrbCX322nIq3Ar4tGQ=','','',NULL,1,'2025-12-29 08:44:56','2025-12-29 08:45:02','2025-12-29 08:45:02',1),(5,'李sir_钱包2','合约','futures',NULL,NULL,'0xd0e74bb1bde3d9bd8ce6ee03c4fb43af84ef7e2a','0xd63616deeA748A3ea1cf163926e8B3eF7C92eCE8','gAAAAABpUj_qJ3snvnIjXQofjcDTxhdzVrWC3g_SvrazPVQU0eM7shTVfzy4FtHrSd2cu9KJmvBhmPOwfiMyuwBAAmnFEs9luDzSboyKxcwkM8VIR5qsGRCnJq6MCEEoRS-4yRz7zVtJvlodVL3d2wgkD6lZWJ4NXcF1fQVSoveM-uAuSop2Ehk=',1,'2025-12-29 08:46:34','2025-12-29 08:47:00','2025-12-29 08:47:00',1),(6,'立安','','spot','gAAAAABpUmpjHnnPzb1KPyeG7ITHU1dW-qSce6EMrbpy-O2FgbDuaboT5veKLF-JPqadZIfaC4PUPIpwUYyTr6mqi5AFMn7Ei10O-3w_Aak-nC7jgfJVI0G13hg94-8Jx453bXr0CkkoWdxEavF9Zcu_ug9GuiL9-7TMQ1gRvINSlc4TtO178j4=','gAAAAABpUmpj_42x_8tx4oOjleMRazn_E4ScRKQ1PsnLu9kfOAcagPwIgb3Qo1g47KytLWhGJvhalQH_zDVPlRZpnxi_YAEQ74BNsT_RC7AcFBHQfOv_0GCMjhGLbVrnp7P1f9swdKy-FBgtwIjDjePHDyCaoaGDnHy0INcCSQC-ICQbrkZTVms=','','',NULL,1,'2025-12-29 11:47:47','2025-12-29 11:47:50','2025-12-29 11:47:50',1),(7,'立安','','futures',NULL,NULL,'0xc7ca6ff4765fe8a3f8609fa677ad2ccc5d84b3e0','0x87a56C656B35fDF400A0bD2Ef767008AFD95Ff9D','gAAAAABpUmqKvxFR7WsohmJZuYd6-rCCfvVouGGJKOTZmkB9ZkBKy15MGesjS0tjIcz8cFe-pH3lT5tKIf9zBf0YgeX_eABH_l4GzcRDPDtRnhiUGJepJbkBx4zkVOK22f-m5THDrJ4BAGeIPHZl7QB6n1lP-3u3iz_qEDXI5Dm9c-MJ7mzLJdQ=',1,'2025-12-29 11:48:27','2025-12-29 11:48:29','2025-12-29 11:48:29',1),(8,'李sir_钱包1','','spot','gAAAAABpU8QjPQJkKYvO3qa_Y8g8X_Bqb8P2AL_EYOZnidp-YQWBi7_Ekvcus3v6PZYuOBGMh38cf3baBULfouKGwTECVjPv1cfComfZC0IhACx5JFRdMyrwNY_5EpTiRfYciwkN-_Rak63RcmxQv1yikG3AAHnXtNit3ZmPAg3lEZgYJKs82D8=','gAAAAABpU8QjSx036uEVDviz5PuQYH9VY2cBmvI1gR-zROFuFDCJcJf79S7hlMaklHuSarMXiDa3-r7fmyE68dqk0KGLRDUADf8B2UVa7o8GJOospPX9kL1tl3vq35XbrKoutqkmLg_Um2zLgZCOD7AypoYJJwM4zGxLpXaOnOLBB38ETVPO2bM=','','',NULL,1,'2025-12-30 12:22:59','2025-12-30 12:26:46','2025-12-30 12:26:46',1),(9,'李sir_钱包1','','futures',NULL,NULL,'0xba2b1219025ad45c9b32b6fc57f76369c6966831','0x4720fa6dF8a86B6757B87a8Ff80776AFE8B23551','gAAAAABpU8T1gf2iuuarVRc9c6GjSZcj1O4aqaOfZ-whR3HSU9kHhSarX8GPlFQdMAshTuxlWNjRme9eJVqw5x9qP4DsUvQc59X3_qhwi6hbNT0G4-qBFFZcn1CktFDF3wG63gU7RnlEkROorMpjgzbDs8Jw7TIhTQiKe6NL7KWtpKQipQ4wr80=',1,'2025-12-30 12:26:29','2025-12-30 12:26:34','2025-12-30 12:26:34',1),(10,'海伦_钱包01','','spot','gAAAAABpU9AChb7C88g7twny81XhN2RS5qifGDon2Q8prF5H6PFDc6-sxVqyZ1x9aDpexrAS_Xwe9hXGg9z80LsHHnF9qvVncJzAFc64SUC8VhtgeWPBLjBUFrsw3CH0kj0tVSnoZfVXKutKXrfGPVbyahnCptQFoV9N92cLxkqUM4MqkILpj70=','gAAAAABpU9ACKZX2ZlI8_yU60rWYJoqliW829tY5SI6_MjwxE_uT2ztYjy3dj5ltH4WL3_Yr6Hnkk7I0q6-xj0PeqxtlFEzEheK1nOXf2optqsQ8stdnFvkVmw62VMiP5gjsAWbYZ4u8wzj4Lkp88g0aGFdGMMcgmi6KiTnggoZ1M9-hDWHEY5E=','','',NULL,1,'2025-12-30 13:13:38','2025-12-30 13:13:46','2025-12-30 13:13:46',1),(11,'Kenn_钱包02','','spot','gAAAAABpU9yiXDBTYblEQ-LBYZZv6vWJl7gRH-0HqLvoitemmpChqvdsR2hEG0Bo5tSO9Hl5QtK7sKXXzZWztAsNy50G5oQSvA2tlN-BEfd3UexYyvvGBEogpHoM6VC_1bg6cnIlSMkqzOoxF7z_6rZFJ60d5Fcg5I5KoHOBbbJTFbOZGyFHlPA=','gAAAAABpU9yiJBxq7UZhvPrKtC3jIlQlxtLGGcz3lrtwzwD-FucvhEgRps11INhEPAAHIMMx8dAb-3bK0B_vX_5BsZEJl9gq7nXNzoKIN9p0lWR7Sx2qcgFkoK6OqDq0sL1to7gmYJK79pfgVBNwRSjrR_Qs0xDDPPjqZT3P6t5KJS4EBsJGe0Q=','','',NULL,1,'2025-12-30 14:07:31','2025-12-30 14:09:07','2025-12-30 14:09:07',1),(12,'立安','21','spot','gAAAAABpVCjOXF3lW5BzdGT1wLB1ZNbt6C6VzkVr0pVira_Co3Y9wEr240NXPnR0DvCek5MawaUf4QICueHlF877VsPaZEzgWQ==','gAAAAABpVCjOCR_EXQCVPmBPPKlgHxBbtCOFWErw_YAXqrSKxD_Ux872f8MR1RuWA3KaKHblSngsJcek_pAYrgqUzu11YcLZAg==','','',NULL,1,'2025-12-30 19:32:30','2025-12-30 19:32:30',NULL,2);
/*!40000 ALTER TABLE `wallets` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'aster_auto'
--

--
-- Dumping routines for database 'aster_auto'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-12-31  3:36:59
