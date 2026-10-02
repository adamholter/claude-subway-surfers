import type {On,Timer} from 'claude-code'
const PANE='subway-video'
type Clip={fps:number;width:number;height:number;parts:string[]}
export function register(on:On){
 let frames:string[]=[],fps=20,index=0,playing=true,opened=false,timer:Timer|undefined
 let invalidate:(()=>void)|undefined
 const start=()=>{playing=true;invalidate?.()}
 on('session.start',async($,e,next)=>{
  invalidate=()=>$.ui.invalidate('ui.render')
  const clip=JSON.parse(await $.fs.read(`${$.plugin.root}/assets/frames/clip.json`)) as Clip
  fps=clip.fps
  for(const part of clip.parts)frames.push(...JSON.parse(await $.fs.read(`${$.plugin.root}/assets/frames/${part}`)) as string[])
  await $.command.register({name:'subway',description:'Loop Subway Surfers footage in a side pane',argumentHint:'[close]',immediate:true})
  timer=$.clock.every(Math.round(1000/fps),()=>{
   if(opened&&playing&&frames.length){index=(index+1)%frames.length;invalidate?.()}
  })
  return next(e)
 })
 on('command.run',{command:'subway'},async($,e)=>{
  if(e.args.trim()==='close'){await $.ui.close({id:PANE});return {}}
  const result=await $.ui.open({id:PANE,title:'Subway Surfers',columns:40,rows:36})
  if('deny' in result&&result.deny)return {text:String(result.deny)}
  opened=true;start();return {}
 })
 on('ui.close',{id:PANE},async($,e,next)=>{const result=await next(e);if(!result.deny)opened=false;return result})
 on('session.end',($,e,next)=>{timer?.cancel();return next(e)})
 on('ui.render',{component:'Pane'},($,e,next)=>{
  if(e.requestId!==PANE)return next(e)
  const ui=$.ui.resolve(e),{Box,Button,Text}=ui
  const view='Svg' in ui?ui.Svg({source:frames[index]??'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="568"/>',width:320,height:568,alt:'Subway Surfers gameplay video'}):Text({children:'Open this pane in Claude Desktop to watch the video.'})
  return Box({flexDirection:'column',gap:1,children:[view,Box({flexDirection:'row',gap:2,children:[
   Button({key:'pause',label:playing?'Pause':'Play',onPress:()=>{playing=!playing;invalidate?.()}}),
   Button({key:'restart',label:'Restart',onPress:()=>{index=0;playing=true;invalidate?.()}})
  ]})]})
 })
}
