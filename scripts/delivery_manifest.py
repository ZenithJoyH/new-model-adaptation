#!/usr/bin/env python3
"""Inventory explicitly selected delivery files; no copying, packaging or remote execution."""
import argparse
import hashlib
import json
from pathlib import Path


def build(root, selections):
    root = root.resolve(strict=True)
    files = []
    for item in selections:
        role, separator, name = item.partition('=')
        if not separator or role not in {'launcher','config','source','lock','restore'}:
            raise ValueError('--file requires launcher/config/source/lock/restore=relative/path')
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('delivery files must be relative to --root')
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size == 0:
            raise ValueError('delivery file missing, empty or outside --root')
        files.append({'role':role,'path':str(path.relative_to(root)),
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if not {'launcher','config','source','lock','restore'} <= {f['role'] for f in files}:
        raise ValueError('all five delivery roles are required')
    if len({f['path'] for f in files}) != len(files):
        raise ValueError('duplicate delivery files')
    return {'schema_version':1,'kind':'delivery_manifest','files':files,'image':{'validation':'pending'}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--file',action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        if not args.root.is_absolute() or not args.output.is_absolute():
            raise ValueError('explicit absolute --root/--output required')
        if not args.output.resolve().is_relative_to(args.root.resolve()):
            raise ValueError('manifest must remain inside --root')
        manifest=build(args.root,args.file)
        with args.output.open('x') as stream:
            json.dump(manifest,stream,ensure_ascii=False,indent=2)
            stream.write('\n')
        print(str(args.output))
        return 0
    except (ValueError,OSError) as exc:
        print('Delivery manifest refused: '+str(exc))
        return 2


if __name__=='__main__': raise SystemExit(main())
