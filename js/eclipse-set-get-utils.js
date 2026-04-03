export const SETTER_TYPES=new Set(['SetNode','SetNode [Eclipse]']);export function getLink(graph,linkId){if(linkId==null)return null;if(graph.getLink)return graph.getLink(linkId);if(graph.links instanceof Map)return graph.links.get(linkId);return graph.links?.[linkId]??null;}
export function findRootGraph(graph){if(!graph)return null;return graph.rootGraph||graph;}
function findSubgraphNodeFor(parentGraph,innerNode){if(!parentGraph?._nodes||!innerNode?.graph)return null;for(const n of parentGraph._nodes){if(n.subgraph&&n.subgraph===innerNode.graph)return n;}
return null;}
export function getGraphAncestors(graph){if(!graph)return[];const root=findRootGraph(graph);if(!root||graph===root)return[root];const chain=[graph];const visited=new Set([graph]);let current=graph;while(current!==root){let found=false;for(const n of root._nodes){if(n.subgraph===current){chain.push(root);current=root;found=true;break;}}
if(found)break;const subgraphs=root._subgraphs||root.subgraphs;if(subgraphs){for(const sg of subgraphs.values()){if(sg===current||!sg._nodes)continue;for(const n of sg._nodes){if(n.subgraph===current){if(visited.has(sg)){found=false;break;}
visited.add(sg);chain.push(sg);current=sg;found=true;break;}}
if(found)break;}}
if(!found){if(!chain.includes(root))chain.push(root);break;}}
return chain;}
export function getGraphDescendants(graph,_visited){if(!graph?._nodes)return[];const visited=_visited||new Set();if(visited.has(graph))return[];visited.add(graph);const descendants=[];for(const n of graph._nodes){if(n.subgraph&&!visited.has(n.subgraph)){descendants.push(n.subgraph);descendants.push(...getGraphDescendants(n.subgraph,visited));}}
return descendants;}
function collectNodesOfType(graphs,type){const results=[];for(const g of graphs){if(!g?._nodes)continue;for(const node of g._nodes){if(node.type===type)results.push({node,graph:g});}}
return results;}
function collectSetterNodes(graphs){const results=[];for(const g of graphs){if(!g?._nodes)continue;for(const node of g._nodes){if(SETTER_TYPES.has(node.type))results.push({node,graph:g});}}
return results;}
export function findSetterByName(graph,name){if(!name)return null;for(const g of getGraphAncestors(graph)){if(!g?._nodes)continue;for(const node of g._nodes){if(SETTER_TYPES.has(node.type)&&node.widgets?.[0]?.value===name){return{node,graph:g};}}}
return null;}
export function findGettersByName(graph,name,getterType){if(!name)return[];const graphs=[graph,...getGraphDescendants(graph)];return collectNodesOfType(graphs,getterType).filter(entry=>entry.node.widgets?.[0]?.value===name);}
let _setNameSourceMap=new Map();export function getSetNameSourceMap(){return _setNameSourceMap;}
export function getVisibleSetNames(graph,filterType){const sourceMap=new Map();const ancestors=getGraphAncestors(graph);const entries=collectSetterNodes(ancestors);for(const e of entries){const name=e.node.widgets?.[0]?.value;if(!name)continue;if(filterType&&filterType!=='*'){const setType=e.node.inputs?.[0]?.type;if(setType&&setType!=='*'){const filterTypes=String(filterType).split(',');if(!filterTypes.some(ft=>ft===setType||setType.split(',').includes(ft)))continue;}}
if(!sourceMap.has(name)){sourceMap.set(name,e.graph===graph?'local':'parent');}}
_setNameSourceMap=sourceMap;return[...sourceMap.keys()].sort();}
const MAX_BYPASS_DEPTH=4;export function isSetterActive(graph,setter){if(!setter)return false;if(setter.mode===2||setter.mode===4)return false;if(!setter.inputs?.[0]?.link)return false;let link=getLink(graph,setter.inputs[0].link);if(!link)return false;let originNode=graph.getNodeById?.(link.origin_id);let depth=0;while(originNode&&originNode.mode===4&&depth<MAX_BYPASS_DEPTH){depth++;const outType=originNode.outputs?.[link.origin_slot]?.type;let matchedInput=null;if(originNode.inputs){for(const inp of originNode.inputs){if(inp.link!=null&&(inp.type===outType||inp.type==='*'||outType==='*')){matchedInput=inp;break;}}}
if(!matchedInput||matchedInput.link==null)return false;link=getLink(graph,matchedInput.link);if(!link)return false;originNode=graph.getNodeById?.(link.origin_id);}
return originNode!=null;}
export function resolveBypassedLink(graph,setter){if(!setter?.inputs?.[0]?.link)return null;let link=getLink(graph,setter.inputs[0].link);if(!link)return null;let originNode=graph.getNodeById?.(link.origin_id);let depth=0;while(originNode&&originNode.mode===4&&depth<MAX_BYPASS_DEPTH){depth++;const outType=originNode.outputs?.[link.origin_slot]?.type;let matchedInput=null;if(originNode.inputs){for(const inp of originNode.inputs){if(inp.link!=null&&(inp.type===outType||inp.type==='*'||outType==='*')){matchedInput=inp;break;}}}
if(!matchedInput||matchedInput.link==null)break;link=getLink(graph,matchedInput.link);if(!link)break;originNode=graph.getNodeById?.(link.origin_id);}
return link;}