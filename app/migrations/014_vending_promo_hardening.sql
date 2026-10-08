-- F02: vending promotion transaction hardening marker.
-- Database.migrate() rebuilds the legacy vending transaction table so
-- final amount may be zero for a 100% promotion and stores promo_id.
INSERT OR IGNORE INTO system_meta(key,value)
VALUES('vending_promo_architecture_version','001');
