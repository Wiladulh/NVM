from app.core.db import Database

class IdentityService:
    def __init__(self,db:Database): self.db=db

    def authorize_credential(self,credential_id):
        with self.db.connect() as c:
            r=c.execute(
                "SELECT c.credential_id,c.member_id,c.status,m.status member_status "
                "FROM identity_credentials c JOIN identity_members m ON m.member_id=c.member_id "
                "WHERE c.credential_id=?",
                (credential_id,),
            ).fetchone()
            if not r:
                r=c.execute(
                    "SELECT c.credential_id,c.member_id,c.status,m.status member_status "
                    "FROM credential_registry c JOIN identity_members m ON m.member_id=c.member_id "
                    "WHERE c.credential_id=? AND c.enabled=1",
                    (credential_id,),
                ).fetchone()
        if not r: return {"authorized":False,"reason":"credential_not_found"}
        if r["status"]!="active" or r["member_status"]!="active":
            return {"authorized":False,"reason":"inactive"}
        return {"authorized":True,"credential_id":r["credential_id"],"member_id":r["member_id"],"reason":"authorized"}

    def account_for_credential(self, credential_id):
        auth = self.authorize_credential(credential_id)
        if not auth["authorized"]:
            return {"authorized": False, "reason": auth["reason"]}
        with self.db.connect() as c:
            r = c.execute(
                """SELECT account_id,account_type,status
                   FROM financial_accounts
                   WHERE member_id=? AND status='active'
                   ORDER BY CASE WHEN account_type='savings' THEN 0 ELSE 1 END, created_at
                   LIMIT 1""",
                (auth["member_id"],),
            ).fetchone()
        if not r:
            return {"authorized": False, "reason": "account_not_found"}
        return {"authorized": True, "credential_id": credential_id,
                "member_id": auth["member_id"], "account_id": r["account_id"],
                "account_type": r["account_type"]}
