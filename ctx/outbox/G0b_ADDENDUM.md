STATUS: PARTIAL

# G0b addendum

Observed on Mint at 2026-09-30T22:20:17Z (UTC; Mint local date 2026-10-01). G0_REPORT.md was read first and remains unchanged. Only this addendum was written locally. Mint operations were read-only; no secrets, raw env values, DB rows, or message text were printed.

1. VERIFIED — env-file classification. Both ashley-agent.service and ashley-discord.service use /home/xarvak/.composer-assistant/.env; no different bot EnvironmentFile was found.

| Key | Classification | Behaviour derived from G0 source defaults |
|---|---|---|
| PERIODIC_COGNITION_ENABLED | set-true | Enables AWAKE/NIGHT periodic mechanism (live.ts:74–79). |
| ASHLEY_AFTERGLOW_ENABLED | unset | Defaults enabled (env.ts:138). |
| PROACTIVE_CHECK_INTERVAL_MIN | unset | Defaults 60 minutes, accepted bounds 1–1440 (discord-bot/src/config.ts:152–157). |

These classify the current file and derive source behaviour; they do not independently establish the running process's loaded environment or compiled artifact equivalence. Other execution gates remain independent.

Exact commands:
```sh
ssh mint 'systemctl --user show ashley-agent.service ashley-discord.service -p Id -p EnvironmentFiles -p WorkingDirectory'
ssh mint 'awk '\''function trim(s){gsub(/^[ \t]+|[ \t]+$/,"",s);return s}
BEGIN{keys["PERIODIC_COGNITION_ENABLED"];keys["ASHLEY_AFTERGLOW_ENABLED"];keys["PROACTIVE_CHECK_INTERVAL_MIN"];keys["ASHLEY_SANDBOX_PROJECT_REGISTRY"];keys["COMPOSER_ENV_FILE"]}
{p=index($0,"=");if(!p)next;k=trim(substr($0,1,p-1));if(!(k in keys))next;v=trim(substr($0,p+1));q=substr(v,1,1);if((q=="\""||q==sprintf("%c",39))&&substr(v,length(v),1)==q)v=substr(v,2,length(v)-2);vals[k]=v;seen[k]=1}
END{for(k in keys){if(k=="ASHLEY_SANDBOX_PROJECT_REGISTRY"||k=="COMPOSER_ENV_FILE"){print k,(seen[k]?"present":"unset");continue}if(!seen[k])c="unset";else if(k=="PROACTIVE_CHECK_INTERVAL_MIN"){if(vals[k] !~ /^[0-9]+([.][0-9]+)?$/)c="set-other";else {n=vals[k]+0;c=(n<=15?"set <=15":n<=60?"set 16-60":n<=240?"set 61-240":"set >240")}}else {v=tolower(trim(vals[k]));c=(v=="true"||v=="1"?"set-true":v=="false"||v=="0"?"set-false":"set-other")}print k,c}}'\'' ~/.composer-assistant/.env'
```

2. VERIFIED — source-derived service sidecar selection is /home/xarvak/.composer-assistant/cognitive-v021.db, not conversations/cognitive-v021.db. index.ts:18–21,37–41 invokes production bootstrap without a dataDir override; bootstrap/production.ts:8–19 constructs the production plane; core/data-plane.ts:56–58,103,144–150 derives the root sidecar. agent.ts:154 consumes cognitiveSidecarDbPath. No env key is consulted by that selection. COMPOSER_DATA_DIR and COMPOSER_ENV_FILE are unset in the classified file; ASHLEY_SANDBOX_PROJECT_REGISTRY is present. Presence is reported only, with no values. Source search found no production COMPOSER_DATA_DIR consumer.

The observed ExecStart is /usr/bin/node dist/index.js. UNKNOWN independent loaded-artifact equivalence: this packet does not authorize deployed compiled-source inspection; the source derivation does not certify the running artifact.

Exact commands:
```sh
ssh mint 'awk '\''BEGIN{k="COMPOSER_DATA_DIR"} /^[ \t]*COMPOSER_DATA_DIR[ \t]*=/{seen=1} END{print k,(seen?"present":"unset")}'\'' ~/.composer-assistant/.env'
ssh mint 'systemctl --user cat ashley-agent.service | grep -E "^(ExecStart|EnvironmentFile)="'
ssh mint 'ls -ld ~/.composer-assistant/sandbox/project-roots.json ~/.composer-assistant/cognitive-v021.db ~/.composer-assistant/conversations/cognitive-v021.db'
rg -n 'createProductionDataPlane' apps/agent-service/src --glob '!*.test.ts'
rg -n 'COMPOSER_DATA_DIR' apps/agent-service/src --glob '!*.test.ts'
```
The related COMPOSER_ENV_FILE classification command is included in item 1.

3. VERIFIED — registry locator: core/sandbox/project-registry.ts:36–47 consumes env.sandboxProjectRegistryPath; env.ts:294–297 selects ASHLEY_SANDBOX_PROJECT_REGISTRY or the default ~/.composer-assistant/sandbox/project-roots.json. The inspection resolved the configured path internally on Mint and read only the requested entry's projectId and exportDestinationCanonicalRoot into output. Exactly one project-ashley entry was found; exportDestinationCanonicalRoot is absent/null (Python lookup returned None). No export root PATH is configured in that entry.

UNKNOWN — export folder existence, file/directory counts, and newest mtime: there is no configured exportDestinationCanonicalRoot to inspect. No folder was guessed. The local default registry file exists, but its existence alone is not registry selection evidence.

Exact command:
```sh
ssh mint 'python3 -c '\''import os,json,datetime
env={}
with open(os.path.expanduser("~/.composer-assistant/.env")) as f:
 for line in f:
  k,sep,v=line.strip().partition("=")
  if sep and k=="ASHLEY_SANDBOX_PROJECT_REGISTRY": env[k]=v.strip().strip("\"'\''\'\'''\''")
p=env.get("ASHLEY_SANDBOX_PROJECT_REGISTRY") or os.path.expanduser("~/.composer-assistant/sandbox/project-roots.json")
try:
 with open(p) as f: data=json.load(f)
 entries=data if isinstance(data,list) else data.get("entries",[])
 matches=[e for e in entries if e.get("projectId")=="project-ashley"]
 print("project-ashley matches",len(matches))
 for e in matches:
  root=e.get("exportDestinationCanonicalRoot")
  print("projectId",e.get("projectId"),"exportDestinationCanonicalRoot",root)
  if not isinstance(root,str): continue
  print("folder_exists",os.path.isdir(root))
  if os.path.isdir(root):
   items=list(os.scandir(root))
   print("immediate_files",sum(x.is_file(follow_symlinks=False) for x in items),"immediate_dirs",sum(x.is_dir(follow_symlinks=False) for x in items),"other",sum(not x.is_file(follow_symlinks=False) and not x.is_dir(follow_symlinks=False) for x in items))
   print("newest_child_mtime",datetime.datetime.fromtimestamp(max((x.stat(follow_symlinks=False).st_mtime for x in items),default=os.stat(root).st_mtime),datetime.timezone.utc).isoformat())
except Exception as e: print("registry UNKNOWN",type(e).__name__)
'\'''
```

4. VERIFIED — recursive names/mtimes inventory. Four migration backup DBs exist under migration-backups; each is approximately 68.91 hours old at observation. The migration-backups directory has the same approximate age. The previously inspected backups directory remains absent per G0; this inventory does not establish backup-package completeness or restore readiness.

The inventory also contains installed dependency test snapshots and sandbox source filenames matching backup/snapshot patterns. They are listed as name matches only, not claimed to be data backups. All migration-backups descendants were included even when their names lack the search terms. Ages below are elapsed time since mtime, not an inferred backup creation time.

Exact command:
```sh
ssh mint 'find ~/.composer-assistant \( -iname '\''*backup*'\'' -o -iname '\''*.bak*'\'' -o -iname '\''*snapshot*'\'' -o -path '\''*/migration-backups/*'\'' \) -printf '\''%y\t%p\t%T@\t%TY-%Tm-%TdT%TH:%TM:%TS%Tz\n'\''; date -u +%Y-%m-%dT%H:%M:%SZ'
```

Complete matching inventory (d=directory, f=file; paths, mtimes and derived ages only):
```text
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-28T10:22:47.1830479240+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-28T10:22:47.1840479450+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/diff/src/__snapshots__	2026-09-28T10:22:47.1550473330+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-28T10:22:47.1830479240+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-28T10:22:47.9400639150+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-28T10:22:47.6590579790+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-28T10:22:47.3070505430+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-28T10:22:47.1820479030+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-28T10:22:47.1830479240+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-28T10:22:48.4090737860+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-28T10:22:48.0880670330+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-28T10:22:47.6440576620+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-28T10:22:47.3290510080+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-28T10:22:47.5930565850+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-28T10:22:47.2460492550+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-28T10:22:47.1830479240+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-28T10:22:51.6441414190+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-28T10:22:47.1840479450+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580089710-6b7a31bd/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-28T10:22:48.4790752590+0300	age=62.96h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-28T10:11:45.8166293230+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-28T10:11:45.8166293230+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/diff/src/__snapshots__	2026-09-28T10:11:45.7916301950+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-28T10:11:45.8176292880+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-28T10:11:46.6246011340+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-28T10:11:46.3566104840+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-28T10:11:45.9556244730+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-28T10:11:45.8186292530+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-28T10:11:45.8166293230+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-28T10:11:46.9965881570+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-28T10:11:46.8415935640+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-28T10:11:46.3386111120+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-28T10:11:45.9776237060+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-28T10:11:46.2946126470+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-28T10:11:45.8916267060+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-28T10:11:45.8176292880+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-28T10:11:50.5674636140+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-28T10:11:45.8156293580+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790579431463-ebc7ca98/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-28T10:11:47.0725855060+0300	age=63.14h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-30T03:55:08.8931421660+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-30T03:55:08.8911422170+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/diff/src/__snapshots__	2026-09-30T03:55:08.8641429060+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-30T03:55:08.8911422170+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-30T03:55:09.8051188970+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-30T03:55:09.5351257860+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-30T03:55:09.0741375480+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-30T03:55:08.8931421660+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-30T03:55:08.8881422940+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-30T03:55:10.1791093540+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-30T03:55:10.0151135390+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-30T03:55:09.5281259650+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-30T03:55:09.1071367060+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-30T03:55:09.4661275470+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-30T03:55:08.9841398440+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-30T03:55:08.8911422170+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-30T03:55:12.2860555870+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-30T03:55:08.8911422170+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.72.2-1790729586795-cb395719/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-30T03:55:10.3041061640+0300	age=21.42h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-29T02:19:36.0885062230+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-29T02:19:36.0885062230+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/diff/src/__snapshots__	2026-09-29T02:19:35.9575082820+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-29T02:19:36.0935061450+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-29T02:19:37.4934841230+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-29T02:19:37.2464880110+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-29T02:19:36.7884952170+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-29T02:19:36.1035059870+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-29T02:19:36.0885062230+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-29T02:19:37.9054776390+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-29T02:19:37.6924809910+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-29T02:19:37.2224883890+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-29T02:19:36.8314945400+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-29T02:19:37.1444896170+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-29T02:19:36.4225009720+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-29T02:19:36.0935061450+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-29T02:19:40.0614436550+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-29T02:19:36.0805063490+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.68.0-1790637526325-f4f11c9d/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-29T02:19:38.0964746310+0300	age=47.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-28T10:03:27.4177676000+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-28T10:03:27.4177676000+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/diff/src/__snapshots__	2026-09-28T10:03:27.3877687540+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-28T10:03:27.4177676000+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-28T10:03:30.0946646640+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-28T10:03:29.8756730820+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-28T10:03:27.5517624460+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-28T10:03:27.4227674080+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-28T10:03:27.4167676390+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-28T10:03:30.4326516740+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-28T10:03:30.2516586300+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-28T10:03:29.8636735440+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-28T10:03:27.5747615610+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-28T10:03:29.8156753890+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-28T10:03:27.4877649080+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-28T10:03:27.4177676000+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-28T10:03:33.8325210660+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-28T10:03:27.4167676390+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578922129-89d5bce0/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-28T10:03:30.5136485610+0300	age=63.28h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-28T09:52:08.7791130950+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-28T09:52:08.7761132590+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/diff/src/__snapshots__	2026-09-28T09:52:08.7511146180+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-28T09:52:08.7791130950+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-28T09:52:11.3019760320+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-28T09:52:11.0989870480+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-28T09:52:10.5320178350+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-28T09:52:09.0191000430+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-28T09:52:08.7791130950+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-28T09:52:11.6309581800+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-28T09:52:11.4719668080+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-28T09:52:11.0899875370+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-28T09:52:10.6610108300+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-28T09:52:11.0389903040+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-28T09:52:09.7370610200+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-28T09:52:08.7791130950+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-28T09:52:13.9898302960+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-28T09:52:08.7761132590+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790578267697-6549e797/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-28T09:52:11.7049541640+0300	age=63.47h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-28T10:30:31.7518281160+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-28T10:30:31.7518281160+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/diff/src/__snapshots__	2026-09-28T10:30:31.7278282420+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-28T10:30:31.7518281160+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-28T10:30:32.6618233310+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-28T10:30:32.3988247170+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-28T10:30:31.9408271270+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-28T10:30:31.7688280280+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-28T10:30:31.7518281160+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-28T10:30:32.9928215880+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-28T10:30:32.8398223940+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-28T10:30:32.3848247910+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-28T10:30:31.9638270070+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-28T10:30:32.2998252380+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-28T10:30:31.8648275250+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-28T10:30:31.7518281160+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-28T10:30:36.4928028750+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-28T10:30:31.7508281220+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.66.0-1790580563950-ebafb179/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-28T10:30:33.0728211640+0300	age=62.83h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-29T08:19:56.4999769860+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-29T08:19:56.4999769860+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/diff/src/__snapshots__	2026-09-29T08:19:56.4729783410+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-29T08:19:56.5009769360+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-29T08:19:57.3729331900+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-29T08:19:57.1209458310+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-29T08:19:56.6669686080+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-29T08:19:56.5019768860+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-29T08:19:56.4999769860+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-29T08:19:57.7159159840+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-29T08:19:57.5689233580+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-29T08:19:57.1139461820+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-29T08:19:56.6949672030+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-29T08:19:57.0519492920+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-29T08:19:56.5859726720+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-29T08:19:56.5009769360+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-29T08:19:59.6468191430+0300	age=41.00h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-29T08:19:56.4989770370+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/versions/1.69.0-1790659126292-5f9c0260/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-29T08:19:57.8079113700+0300	age=41.01h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-cover/src/__snapshots__	2026-09-28T09:14:17.8770114620+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-flip/src/__snapshots__	2026-09-28T09:14:17.6299989150+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/diff/src/__snapshots__	2026-09-28T09:14:18.1660261190+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-circle/src/__snapshots__	2026-09-28T09:14:18.0030178630+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-color/src/__snapshots__	2026-09-28T09:14:19.4640917950+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-color/src/__image_snapshots__	2026-09-28T09:14:19.1350751800+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-quantize/src/__image_snapshots__	2026-09-28T09:14:18.5200440490+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-threshold/src/__image_snapshots__	2026-09-28T09:14:17.5909969340+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-fisheye/src/__snapshots__	2026-09-28T09:14:17.6509999820+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-blit/src/__snapshots__	2026-09-28T09:14:20.3531366390+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-blit/src/__image_snapshots__	2026-09-28T09:14:20.1731275750+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-blur/src/__image_snapshots__	2026-09-28T09:14:19.1340751290+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-crop/src/__snapshots__	2026-09-28T09:14:18.3380348310+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/js-png/src/__image_snapshots__	2026-09-28T09:14:19.1230745730+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-rotate/src/__snapshots__	2026-09-28T09:14:17.7800065350+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-contain/src/__snapshots__	2026-09-28T09:14:17.9100131390+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-print/src/__image_snapshots__	2026-09-28T09:14:22.1822285320+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-mask/src/__snapshots__	2026-09-28T09:14:17.6299989150+0300	age=64.10h
d	/home/xarvak/.composer-assistant/sandbox/command-code/node_modules/@jimp/plugin-resize/src/__snapshots__	2026-09-28T09:14:20.1301254100+0300	age=64.10h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/scripts/backup-memory.ps1	2026-09-28T11:01:26.1880357880+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/scripts/snapshot-incident-c.mjs	2026-09-28T11:01:26.1890357430+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/scripts/snapshot-incident-c.test.mjs	2026-09-28T11:01:26.1910356530+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/apps/discord-bot/src/handlers/message-snapshot-semantics.test.ts	2026-09-28T11:01:26.1950354740+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/apps/agent-service/src/core/continuity/backup-package.ts	2026-09-28T11:01:26.2130346660+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/apps/agent-service/src/core/continuity/backup-restore-falsifiers.test.ts	2026-09-28T11:01:26.2130346660+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/apps/sandbox-v2/src/verification/snapshot.test.ts	2026-09-28T11:01:26.2770317940+0300	age=62.31h
f	/home/xarvak/.composer-assistant/sandbox/workspaces/XJo6RdfAdEeXhUvyNyx9XQ/tree/apps/sandbox-v2/src/verification/snapshot.ts	2026-09-28T11:01:26.2770317940+0300	age=62.31h
d	/home/xarvak/.composer-assistant/migration-backups	2026-09-28T04:25:41.4464584620+0300	age=68.91h
f	/home/xarvak/.composer-assistant/migration-backups/nuclear-v14-pre15-2026-09-28T01-25-40-936Z-17026fcb.db	2026-09-28T04:25:40.9544766180+0300	age=68.91h
f	/home/xarvak/.composer-assistant/migration-backups/nuclear-v21-pre22-2026-09-28T01-25-41-406Z-272914f7.db	2026-09-28T04:25:41.4404586830+0300	age=68.91h
f	/home/xarvak/.composer-assistant/migration-backups/nuclear-v12-pre13-2026-09-28T01-25-40-706Z-68b23f5e.db	2026-09-28T04:25:40.7174853810+0300	age=68.91h
f	/home/xarvak/.composer-assistant/migration-backups/nuclear-v13-pre14-2026-09-28T01-25-40-863Z-77ab525f.db	2026-09-28T04:25:40.8764795020+0300	age=68.91h
```

Key lines:
```text
PERIODIC_COGNITION_ENABLED=set-true
ASHLEY_AFTERGLOW_ENABLED=unset (source default enabled)
PROACTIVE_CHECK_INTERVAL_MIN=unset (source default 60 minutes)
SOURCE_DERIVED_SIDECAR=/home/xarvak/.composer-assistant/cognitive-v021.db
RUNNING_ARTIFACT_EQUIVALENCE=UNKNOWN
PROJECT_ASHLEY_REGISTRY_ENTRY=present (one)
PROJECT_ASHLEY_EXPORT_ROOT=absent/null
EXPORT_FOLDER_COUNTS=UNKNOWN (no configured root)
MIGRATION_BACKUP_DB_FILES=4
NEWEST_MIGRATION_BACKUP_MTIME=2026-09-28T04:25:41.4404586830+0300
```

