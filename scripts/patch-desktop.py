#!/usr/bin/env python3
"""Patch only an explicitly supplied copy of Claude Desktop. Original app stays signed."""
import argparse,hashlib,json,pathlib,plistlib,struct
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('app',help='A separate copy of Claude Desktop to patch')
parser.add_argument('--source',default='/Applications/Claude.app',help='The original, unmodified Claude Desktop app')
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
app=pathlib.Path(args.app).resolve()
source_app=pathlib.Path(args.source).resolve()
if app==source_app or app==pathlib.Path('/Applications/Claude.app'):
    raise SystemExit('Use a separate app copy')
resources=app/'Contents/Resources'
archive=resources/'app.asar'
raw=(source_app/'Contents/Resources/app.asar').read_bytes()
_,header_size,_,json_size=struct.unpack('<4I',raw[:16])
header=json.loads(raw[16:16+json_size])
entries=[]
def collect(node,prefix=''):
    for name,item in node.get('files',{}).items():
        location=f'{prefix}/{name}'.lstrip('/')
        if 'files' in item:collect(item,location)
        elif 'offset' in item:entries.append((location,item))
collect(header)
entries.sort(key=lambda entry:int(entry[1]['offset']))
payload=bytearray()
for name,item in entries:
    content=raw[8+header_size+int(item['offset']):8+header_size+int(item['offset'])+item['size']]
    if name=='package.json':
        package=json.loads(content);package['productName']='Claude Sidecar';content=json.dumps(package).encode()
    if name=='.vite/build/index.pre.js':content+=b'\nrequire("./subway-main.cjs");\n'
    item['offset']=str(len(payload));item['size']=len(content)
    if 'integrity' in item:
        block=item['integrity']['blockSize']
        item['integrity']={'algorithm':'SHA256','hash':hashlib.sha256(content).hexdigest(),'blockSize':block,'blocks':[hashlib.sha256(content[i:i+block]).hexdigest() for i in range(0,len(content),block)]}
    payload.extend(content)
content=('require('+json.dumps(str(root/'desktop/subway-main.cjs'))+');').encode()
header['files']['.vite']['files']['build']['files']['subway-main.cjs']={'size':len(content),'offset':str(len(payload)),'integrity':{'algorithm':'SHA256','hash':hashlib.sha256(content).hexdigest(),'blockSize':4194304,'blocks':[hashlib.sha256(content).hexdigest()]}}
payload.extend(content)
encoded=json.dumps(header,separators=(',',':'),ensure_ascii=False).encode()
padding=b'\0'*((-len(encoded))%4)
pickle=struct.pack('<II',4+len(encoded)+len(padding),len(encoded))+encoded+padding
archive.write_bytes(struct.pack('<II',4,len(pickle))+pickle+payload)
info_path=app/'Contents/Info.plist'
with info_path.open('rb') as file:info=plistlib.load(file)
info['ElectronAsarIntegrity']={'Resources/app.asar':{'algorithm':'SHA256','hash':hashlib.sha256(encoded).hexdigest()}}
info['CFBundleIdentifier']='com.adam.claude-sidecar'
info['CFBundleName']='Claude Sidecar'
info['CFBundleDisplayName']='Claude Sidecar'
old_executable=info['CFBundleExecutable']
new_executable='Claude Sidecar'
if (app/'Contents/MacOS'/old_executable).exists() and old_executable!=new_executable:
    (app/'Contents/MacOS'/old_executable).rename(app/'Contents/MacOS'/new_executable)
info['CFBundleExecutable']=new_executable
with info_path.open('wb') as file:plistlib.dump(info,file)
for helper in (app/'Contents/Frameworks').glob('Claude Helper*.app'):
    helper_info=helper/'Contents/Info.plist'
    with helper_info.open('rb') as file:details=plistlib.load(file)
    old=details['CFBundleExecutable'];new=old.replace('Claude Helper','Claude Sidecar Helper')
    (helper/'Contents/MacOS'/old).rename(helper/'Contents/MacOS'/new)
    details['CFBundleExecutable']=new
    details['CFBundleName']=new
    details['CFBundleDisplayName']=new
    details['CFBundleIdentifier']=details['CFBundleIdentifier'].replace('com.anthropic.claudefordesktop','com.adam.claude-sidecar')
    with helper_info.open('wb') as file:plistlib.dump(details,file)
    helper.rename(helper.with_name(helper.name.replace('Claude Helper','Claude Sidecar Helper')))
for source,target in [('desktop/pane.js','subway-pane.js'),('assets/subway-gameplay.mp4','subway-gameplay.mp4')]:
    (resources/target).write_bytes((root/source).read_bytes())
print(f'Patched {app}')
