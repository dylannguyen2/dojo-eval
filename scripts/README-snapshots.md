## Seeding snapshots

You can seed snapshots for tasks or initial data with `seed.py`.
This will craete the mongodb snapshot, meiliserach snapshot and search indexes.

See what changes would be made
`uv run seed.py remote --path ../dojo-bench-customer-colossus/initial-backend-data/[spa_name]  --env staging --dry-run`

Create snapshot for tasks
`uv run seed.py remote --path ../dojo-bench-customer-colossus/initial-backend-data/[spa_name]  --env staging`

To overwrite existing snapshots for jd tasks
`uv run seed.py remote --path ../dojo-bench-customer-colossus/initial-backend-data/jd  --env staging  --overwrite`

## Creating permanent sessions

The SPAs demos use permanent sessions.
If you updated the initial data and reseeded it you should also update the sessions in `../config/spa-session-ids.json`

To create the permanent sessions run
`uv run create-permanent-sessions.py --env staging`

and then update the config with the output. The SPAs will auto deploy after the next push. It may take sometime for cloudflare cache to be invalidated.
If you are in a hurry you can use `invalidate_cloudfront.sh` to speed it up.

**IMPORTANT: To create permanent session your dojo org has to have `can_create_session` permission**

## Veryfing snapshot status

Check all apps in staging
`python scripts/check_snapshot_status.py --env staging`

Check all apps in production
`python scripts/check_snapshot_status.py --env production`

Check only JD app in staging
`python scripts/check_snapshot_status.py --env staging --app jd`

Check only Weibo app
`python scripts/check_snapshot_status.py --env staging --app weibo`

Check only Xiaohongshu app
`python scripts/check_snapshot_status.py --env staging --app xiaohongshu`

The script will automatically:

- Switch to the correct kubectl context
- Scan all \*.json files in dojo-bench-customer-colossus/initial-backend-data/{app}/
- Calculate the expected snapshot name using the same logic as seed.py
- Compare with git history to detect if backend files were modified after snapshot creation
- Mark snapshots as [OUTDATED] if they need to be regenerated

**WARNING: Do not run this councurrently becuase this changes kubctl context**
