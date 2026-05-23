# Secret Rotation Runbook

> Use this when rotating any of the production secrets, or when responding to
> a suspected leak. The first rotation should happen now because the
> credentials below were committed to git.

---

## What needs rotating

| Secret | Lives in | Used by | Rotation impact |
|---|---|---|---|
| `SECRET_KEY` | EB env vars | Django session signer | Logs every user out once. No data loss. |
| `EMAIL_API_SECRET_KEY` (Django) / `API_SECRET_KEY` (Lambda) | EB env vars + Lambda env vars | Lambda → Django auth | Email pipeline broken until both sides match. |
| `RDS_PASSWORD` | EB env vars + RDS itself | Django → RDS connection | ~30s of 5xx during rolling deploy. |
| `XERO_ENCRYPTION_KEY` | EB env vars | Encrypts Xero OAuth tokens at rest | **DESTRUCTIVE.** Every Xero connection must be re-authorised. Plan separately. |

The leaked values you should treat as compromised:

- `SECRET_KEY` (had a `django-insecure-…` default in `base.py`/`production_aws.py`)
- `XERO_ENCRYPTION_KEY = yGUzgEzWkkCsHnb_lof7bmX0m8gBc3917sHYU2SYe8A=`
- `EMAIL_API_SECRET_KEY = 05817a8c12b4f2d5b173953b3a0ab58a70a2f18b84ceaed32326e7e87cf6ed0e`
- `RDS_PASSWORD` candidates: `DevApp2024SecurePass!` and `U1wPqDKuRZVZ6hwRrLkrpnNp` (the two scripts disagreed; whichever one is live in EB right now is the one that matters).

---

## Step 1 — `SECRET_KEY`

```bash
# Generate a new value (64 random url-safe chars).
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Copy the output and set it on the EB environment.
eb setenv SECRET_KEY='<paste-value-here>'

# EB will roll the env. Watch the deploy.
eb status
```

After the deploy: every active session is invalidated; users have to log in
again. That's expected.

---

## Step 2 — `EMAIL_API_SECRET_KEY`

Two systems must hold the same value. **Update both before testing.**

```bash
# 1. Generate a new value.
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
NEW_KEY='<paste-value-here>'

# 2. Update Django (EB env). Django expects the var name EMAIL_API_SECRET_KEY.
eb setenv EMAIL_API_SECRET_KEY="$NEW_KEY"

# 3. Update Lambda. The current code reads `API_SECRET_KEY`. Rename it to
#    EMAIL_API_SECRET_KEY at the same time so both sides agree.
aws lambda update-function-configuration \
  --function-name email-processor \
  --region us-east-1 \
  --environment "Variables={EMAIL_API_SECRET_KEY=$NEW_KEY,DJANGO_API_URL=https://app.mason.build/core/api/receive_email/}"

# 4. Edit lambda_function.py:26 to read 'EMAIL_API_SECRET_KEY' (was
#    'API_SECRET_KEY'), zip it, and `aws lambda update-function-code`.
```

Once both are updated, send a test email to a `*@mail.mason.build` address
and confirm it lands in the Bills Inbox.

---

## Step 3 — `RDS_PASSWORD`

```bash
# 1. Generate a strong password (RDS allows up to 128 chars; avoid /, @, ", space).
python3 -c "import secrets, string; \
  alphabet = string.ascii_letters + string.digits + '!#%^*-_=+'; \
  print(''.join(secrets.choice(alphabet) for _ in range(40)))"

# 2. Modify the RDS master password.
aws rds modify-db-instance \
  --db-instance-identifier <your-rds-instance-id> \
  --master-user-password '<paste-value-here>' \
  --apply-immediately

# 3. Wait for `aws rds describe-db-instances` to show DBInstanceStatus=available.

# 4. Update EB so Django uses the new password.
eb setenv RDS_PASSWORD='<paste-value-here>'

# 5. Verify the app comes back: eb status, then hit /admin/.
```

Brief downtime is normal. If you have multiple AWS environments (staging,
prod) repeat for each.

---

## Step 4 — `XERO_ENCRYPTION_KEY` (don't do this casually)

This key encrypts the Xero OAuth refresh tokens stored in the
`XeroInstances` table. Rotating it means every existing token cannot be
decrypted, so **every Xero connection has to be re-authorised by hand** in
the UI after rotation.

When you do rotate:

1. Generate: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. Pre-stage by adding it as an *additional* key (currently the code only
   supports one key — see `core/models.py XeroInstances._get_cipher`). This
   needs a small code change before rotation is non-destructive.
3. Wipe the existing encrypted tokens, push the new key, then have each
   project owner reconnect to Xero.

Until the multi-key setup exists, leave this key alone. The committed key is
useless without DB access.

---

## Step 5 — scrub history (optional, destructive)

The leaked values still live in `git log`. Two choices:

- **Live with it.** The values are no longer valid post-rotation, so a
  history-rewrite isn't strictly required. This is what most teams do.
- **Scrub.** Use `git filter-repo` (or BFG Repo-Cleaner) to delete the
  offending blobs and force-push. This rewrites every commit hash and
  invalidates every open PR/clone. Coordinate before doing it.

```bash
# Example with git filter-repo (one-shot, irreversible):
pip install git-filter-repo
git filter-repo --path set_eb_env_vars.sh --path set_rds_env_vars.sh --invert-paths
git filter-repo --replace-text <(echo '05817a8c12b4f2d5b173953b3a0ab58a70a2f18b84ceaed32326e7e87cf6ed0e==>REDACTED')
git push origin --force --all
git push origin --force --tags
```

---

## Verification checklist

After rotation:

- [ ] `eb printenv | grep -E 'SECRET_KEY|EMAIL_API|RDS_PASSWORD|XERO_ENC'` shows new values.
- [ ] Login works (you'll have to log in again).
- [ ] An email to `*@mail.mason.build` appears in Bills Inbox.
- [ ] A protected admin endpoint (`/admin/`) is reachable.
- [ ] `aws rds describe-db-instances` shows `available`.
- [ ] (optional) `dev_app/settings/production_aws.py` no longer contains a
      `default=` argument anywhere — verified by `grep -n "os.getenv(.*,'.*')" dev_app/settings/production_aws.py`.
- [ ] Old test scripts in repo (`test_email_sender.py`, `test_email_locally.py`) read `EMAIL_API_SECRET_KEY` from env — verified by grep.
