import { afterEach, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { mountGovernance } from '../../app/enterprise/static/governance_app.js';

let mounted;
afterEach(()=>{mounted?.dispose();vi.restoreAllMocks();});
const tick=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
const response=(data,status=200)=>({ok:status<300,status,json:async()=>data});

it('reuses the exact command after a committed create loses its response',async()=>{
  document.body.innerHTML=readFileSync('app/enterprise/static/governance_index.html','utf8');
  document.cookie='gov_csrf=synthetic; Path=/';
  const posts=[];
  const fetcher=vi.fn(async(url,options)=>{
    if(options.method==='POST'){
      posts.push(JSON.parse(options.body));
      if(posts.length===1)throw new Error('Synthetic committed-response transport failure');
      return response({id:'10000000-0000-4000-8000-000000000001',revision:1,state:'draft',data:{}});
    }
    return response(url.endsWith('/me')?{id:'steward',roles:['data_steward'],departments:['operations'],csrf_cookie_name:'gov_csrf'}:{policy:{type:'object',properties:{}}});
  });
  mounted=await mountGovernance(document,fetcher);
  const editor=document.getElementById('gov-editor');
  editor.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await tick();
  editor.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await tick();
  expect(posts).toHaveLength(2);
  expect(posts[0]).toEqual(posts[1]);
  document.getElementById('gov-new').click();
  editor.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await tick();
  expect(posts[2].command_key).not.toBe(posts[1].command_key);
});
