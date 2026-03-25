import { app } from './comfy/index.js';
import { patchNodeCSSSize } from './eclipse-widget-performance-utils.js';
function getElFunction() {
    return 'function' == typeof $el
        ? $el
        : function (e, o, t) {
              let n = o;
              Array.isArray(o) && ((t = o), (n = {}));
              const [i, ...l] = e.split('.'),
                  s = document.createElement(i);
              for (const e of l) s.classList.add(e);
              if (n) {
                  n.style && Object.assign(s.style, n.style);
                  for (const [e, o] of Object.entries(n))
                      'style' !== e &&
                          (e.startsWith('on') && 'function' == typeof o
                              ? s.addEventListener(e.slice(2).toLowerCase(), o)
                              : 'children' !== e && (s[e] = o));
              }
              if (t)
                  for (const e of t)
                      'string' == typeof e
                          ? s.appendChild(document.createTextNode(e))
                          : e instanceof Node && s.appendChild(e);
              return s;
          };
}
function rgbToHex(e, o, t) {
    return '#' + ((1 << 24) + (e << 16) + (o << 8) + t).toString(16).slice(1);
}
// Console helper: eclipse_rgb(149, 69, 228) → "#9545e4"
window.eclipse_rgb = (r, g, b) => {
    const hex = rgbToHex(Math.round(r), Math.round(g), Math.round(b));
    console.log(`rgb(${r}, ${g}, ${b}) → ${hex}`);
    return hex;
};
function shadeHexColor(e, o = -0.2) {
    e.startsWith('#') && (e = e.slice(1));
    let t = parseInt(e.slice(0, 2), 16),
        n = parseInt(e.slice(2, 4), 16),
        i = parseInt(e.slice(4, 6), 16);
    return (
        (t = Math.max(0, Math.min(255, t + 100 * o))),
        (n = Math.max(0, Math.min(255, n + 100 * o))),
        (i = Math.max(0, Math.min(255, i + 100 * o))),
        rgbToHex(t, n, i)
    );
}
let afterChange;
function invokeAfterChange() {
    return afterChange?.apply(this, arguments);
}
function setColorMode(e, o) {
    o.graph._nodes.forEach((e) => {
        ((e.bgcolor = e._bgcolor ?? e.bgcolor), (e.color = e._color ?? e.color), e.setDirtyCanvas(!0, !0));
    });
}
let loading = !1;
if (
    (app.registerExtension({
        name: 'Eclipse.ForceBoxNodes',
        async init(e) {
            e.ui.settings.addSetting({
                id: 'Eclipse.ForceBoxNodes',
                name: '📦 Eclipse Force Box Nodes',
                type: 'boolean',
                tooltip: 'Remove rounded corners - nodes will always be boxes.',
                defaultValue: !1,
                onChange(o) {
                    ((e.canvas.round_radius = o ? 0 : 8), e.graph.setDirtyCanvas(!0, !0));
                },
            });
        },
    }),
    app.registerExtension({
        name: 'Eclipse.LogLevel',
        async init(e) {
            let o = 'warning';
            try {
                const e = await fetch('/eclipse/config/log_level');
                if (e.ok) {
                    o = (await e.json()).log_level || 'warning';
                }
            } catch (e) {
                console.error('[Eclipse] Failed to fetch log level:', e);
            }
            e.ui.settings.addSetting({
                id: 'Eclipse.LogLevel',
                name: '📝 Eclipse Log Level',
                type: 'combo',
                tooltip:
                    'Set the logging verbosity level. Changes are saved to config.json and applied immediately.\n\nerror: Only critical errors\nwarning: Errors + warnings\ninfo: Errors + warnings + general messages\ndebug: All messages including detailed debug info',
                defaultValue: o,
                options: ['error', 'warning', 'info', 'debug'],
                async onChange(e) {
                    try {
                        const o = await fetch('/eclipse/config/log_level', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ log_level: e }),
                        });
                        if (o.ok) {
                            const t = await o.json();
                            t.success
                                ? console.log(`[Eclipse] Log level changed to: ${e}`)
                                : console.error('[Eclipse] Failed to update log level:', t.error);
                        } else console.error('[Eclipse] Server error updating log level:', o.status);
                    } catch (e) {
                        console.error('[Eclipse] Failed to update log level:', e);
                    }
                },
            });
        },
    }),
    app.registerExtension({
        name: 'Eclipse.DevMode',
        async init(e) {
            let o = !1;
            try {
                const e = await fetch('/eclipse/config/dev_mode');
                if (e.ok) {
                    o = (await e.json()).dev_mode || !1;
                }
            } catch (e) {
                console.error('[Eclipse] Failed to fetch dev mode:', e);
            }
            let t = !1;
            e.ui.settings.addSetting({
                id: 'Eclipse.DevMode',
                name: '🛠️ Eclipse Dev Mode',
                type: 'boolean',
                tooltip:
                    'Enable development mode. Changes are saved to config.json.',
                defaultValue: o,
                async onChange(e) {
                    if (t)
                        try {
                            const o = await fetch('/eclipse/config/dev_mode', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ dev_mode: e }),
                            });
                            if (o.ok) {
                                const t = await o.json();
                                t.success
                                    ? console.log('[Eclipse] Dev mode ' + (e ? 'enabled' : 'disabled'))
                                    : console.error('[Eclipse] Failed to update dev mode:', t.error);
                            } else console.error('[Eclipse] Server error updating dev mode:', o.status);
                        } catch (e) {
                            console.error('[Eclipse] Failed to update dev mode:', e);
                        }
                    else t = !0;
                },
            });
        },
    }),
    app.registerExtension({
        name: 'Eclipse.VueSizeFix',
        async init(e) {
            let o = !0;
            try {
                const e = await fetch('/eclipse/config/all');
                if (e.ok) {
                    o = !1 !== (await e.json()).vue_size_fix;
                }
            } catch (e) {
                console.error('[Eclipse] Failed to fetch vue_size_fix:', e);
            }
            let t = !1;
            e.ui.settings.addSetting({
                id: 'Eclipse.VueSizeFix',
                name: '📐 Eclipse Vue Size Fix',
                type: 'boolean',
                tooltip:
                    'Fix collapsed node width and z-ordering in Vue renderer. Prevents nodes from being too wide when collapsed and fixes z-order flattening on workflow load. Requires page reload after changing.',
                defaultValue: o,
                async onChange(e) {
                    if (t)
                        try {
                            const o = await fetch('/eclipse/config/update', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ vue_size_fix: e }),
                            });
                            if (o.ok) {
                                (await o.json()).success &&
                                    console.log(
                                        `[Eclipse] Vue size fix ${e ? 'enabled' : 'disabled'} (reload required)`,
                                    );
                            }
                        } catch (e) {
                            console.error('[Eclipse] Failed to update vue_size_fix:', e);
                        }
                    else t = !0;
                },
            });
        },
    }),
    app.registerExtension({
        name: 'Eclipse.UseSliders',
        async init(e) {
            let o = !0;
            try {
                const e = await fetch('/eclipse/config/all');
                if (e.ok) {
                    o = !1 !== (await e.json()).use_sliders;
                }
            } catch (e) {
                console.error('[Eclipse] Failed to fetch use_sliders:', e);
            }
            let t = !1;
            e.ui.settings.addSetting({
                id: 'Eclipse.UseSliders',
                name: '🎚️ Eclipse Use Sliders',
                type: 'boolean',
                tooltip:
                    'Show numeric inputs as sliders instead of plain number fields in Eclipse nodes (steps, cfg, guidance, denoise, etc.). Requires restart after changing.',
                defaultValue: o,
                async onChange(e) {
                    if (t)
                        try {
                            const o = await fetch('/eclipse/config/update', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ use_sliders: e }),
                            });
                            if (o.ok) {
                                (await o.json()).success &&
                                    console.log(
                                        `[Eclipse] Use sliders ${e ? 'enabled' : 'disabled'} (restart required)`,
                                    );
                            }
                        } catch (e) {
                            console.error('[Eclipse] Failed to update use_sliders:', e);
                        }
                    else t = !0;
                },
            });
        },
    }),
    app.registerExtension({
        name: 'Eclipse.colors',
        async setup(e) {
            const o = +(window.localStorage.getItem('Comfy.Settings.Eclipse.colors') ?? '0');
            (e.graph._nodes.forEach((e) => {
                ((e._bgcolor = e._bgcolor ?? e.bgcolor), (e._color = e._color ?? e.color));
            }),
                setColorMode(o, e));
        },
        loadedGraphNode(e, o) {
            ((e._bgcolor = e._bgcolor ?? e.bgcolor),
                (e._color = e._color ?? e.color),
                loading ||
                    ((loading = !0),
                    setTimeout(function () {
                        loading = !1;
                        setColorMode(+(window.localStorage.getItem('Comfy.Settings.Eclipse.colors') ?? '0'), o);
                    }, 500)));
        },
        async init(e) {
            ((afterChange = e.graph.afterChange), (e.graph.afterChange = invokeAfterChange));
            const o = LGraphCanvas.onMenuNodeColors;
            'function' == typeof o
                ? (LGraphCanvas.onMenuNodeColors = function (e, t, n, i, l) {
                      const s = o.apply(this, arguments),
                          a = getElFunction(),
                          r = i?.current_submenu?.root;
                      if (!r) return (console.debug('[Eclipse.colors] Could not access menu submenu root'), s);
                      const c = l instanceof LGraphGroup;
                      try {
                          (c ||
                              (r.append(
                                  a('div.litemenu-entry.submenu', [
                                      a(
                                          'label',
                                          {
                                              style: {
                                                  position: 'relative',
                                                  overflow: 'hidden',
                                                  display: 'block',
                                                  paddingLeft: '4px',
                                                  borderLeft: '8px solid #222',
                                              },
                                          },
                                          [
                                              'Custom Title',
                                              a('input', {
                                                  type: 'color',
                                                  value: l.bgcolor,
                                                  style: { position: 'absolute', right: '200%' },
                                                  oninput(e) {
                                                      ((l.color = shadeHexColor(e.target.value)),
                                                          l.setDirtyCanvas(!0, !0));
                                                  },
                                                  onchange(e) {
                                                      console.log(`[Eclipse] Title: ${l.color}`);
                                                  },
                                              }),
                                          ],
                                      ),
                                  ]),
                              ),
                              r.append(
                                  a('div.litemenu-entry.submenu', [
                                      a(
                                          'label',
                                          {
                                              style: {
                                                  position: 'relative',
                                                  overflow: 'hidden',
                                                  display: 'block',
                                                  paddingLeft: '4px',
                                                  borderLeft: '8px solid #222',
                                              },
                                          },
                                          [
                                              'Custom BG',
                                              a('input', {
                                                  type: 'color',
                                                  value: l.bgcolor,
                                                  style: { position: 'absolute', right: '200%' },
                                                  oninput(e) {
                                                      ((l.bgcolor = e.target.value), l.setDirtyCanvas(!0, !0));
                                                  },
                                                  onchange(e) {
                                                      console.log(`[Eclipse] BG: ${e.target.value}`);
                                                  },
                                              }),
                                          ],
                                      ),
                                  ]),
                              ),
                              r.append(
                                  a('div.litemenu-entry.submenu', [
                                      a(
                                          'label',
                                          {
                                              style: {
                                                  position: 'relative',
                                                  overflow: 'hidden',
                                                  display: 'block',
                                                  paddingLeft: '4px',
                                                  borderLeft: '8px solid #222',
                                              },
                                          },
                                          [
                                              'Custom All',
                                              a('input', {
                                                  type: 'color',
                                                  value: l.bgcolor,
                                                  style: { position: 'absolute', right: '200%' },
                                                  oninput(e) {
                                                      ((l.bgcolor = e.target.value),
                                                          (l.color = shadeHexColor(l.bgcolor)),
                                                          l.setDirtyCanvas(!0, !0));
                                                  },
                                                  onchange(e) {
                                                      console.log(`[Eclipse] All \u2192 BG: ${l.bgcolor}, Title: ${l.color}`);
                                                  },
                                              }),
                                          ],
                                      ),
                                  ]),
                              )),
                              c &&
                                  (r.append(
                                      a('div.litemenu-entry.submenu', [
                                          a(
                                              'label',
                                              {
                                                  style: {
                                                      position: 'relative',
                                                      overflow: 'hidden',
                                                      display: 'block',
                                                      paddingLeft: '4px',
                                                      borderLeft: '8px solid #222',
                                                  },
                                              },
                                              [
                                                  'Color Group',
                                                  a('input', {
                                                      type: 'color',
                                                      value: l.bgcolor,
                                                      style: { position: 'absolute', right: '200%' },
                                                      oninput(e) {
                                                          ((l.bgcolor = e.target.value),
                                                              (l.color = shadeHexColor(l.bgcolor)),
                                                              l.setDirtyCanvas(!0, !0));
                                                      },
                                                  }),
                                              ],
                                          ),
                                      ]),
                                  ),
                                  r.append(
                                      a('div.litemenu-entry.submenu', [
                                          a(
                                              'label',
                                              {
                                                  style: {
                                                      position: 'relative',
                                                      overflow: 'hidden',
                                                      display: 'block',
                                                      paddingLeft: '4px',
                                                      borderLeft: '8px solid #222',
                                                  },
                                              },
                                              [
                                                  'Color All Title',
                                                  a('input', {
                                                      type: 'color',
                                                      value: l.bgcolor,
                                                      style: { position: 'absolute', right: '200%' },
                                                      oninput(e) {
                                                          (l.recomputeInsideNodes(),
                                                              (l.color = shadeHexColor(e.target.value)),
                                                              l._nodes.forEach((o) => {
                                                                  ((o.color = shadeHexColor(e.target.value)),
                                                                      o.setDirtyCanvas(!0, !0));
                                                              }),
                                                              l.setDirtyCanvas(!0, !0));
                                                      },
                                                  }),
                                              ],
                                          ),
                                      ]),
                                  ),
                                  r.append(
                                      a('div.litemenu-entry.submenu', [
                                          a(
                                              'label',
                                              {
                                                  style: {
                                                      position: 'relative',
                                                      overflow: 'hidden',
                                                      display: 'block',
                                                      paddingLeft: '4px',
                                                      borderLeft: '8px solid #222',
                                                  },
                                              },
                                              [
                                                  'Color All BG',
                                                  a('input', {
                                                      type: 'color',
                                                      value: l.bgcolor,
                                                      style: { position: 'absolute', right: '200%' },
                                                      oninput(e) {
                                                          (l.recomputeInsideNodes(),
                                                              (l.bgcolor = e.target.value),
                                                              l._nodes.forEach((o) => {
                                                                  ((o.bgcolor = e.target.value),
                                                                      o.setDirtyCanvas(!0, !0));
                                                              }),
                                                              l.setDirtyCanvas(!0, !0));
                                                      },
                                                  }),
                                              ],
                                          ),
                                      ]),
                                  ),
                                  r.append(
                                      a('div.litemenu-entry.submenu', [
                                          a(
                                              'label',
                                              {
                                                  style: {
                                                      position: 'relative',
                                                      overflow: 'hidden',
                                                      display: 'block',
                                                      paddingLeft: '4px',
                                                      borderLeft: '8px solid #222',
                                                  },
                                              },
                                              [
                                                  'Color All',
                                                  a('input', {
                                                      type: 'color',
                                                      value: l.bgcolor,
                                                      style: { position: 'absolute', right: '200%' },
                                                      oninput(e) {
                                                          (l.recomputeInsideNodes(),
                                                              (l.bgcolor = e.target.value),
                                                              (l.color = shadeHexColor(l.bgcolor)),
                                                              l._nodes.forEach((o) => {
                                                                  ((o.bgcolor = e.target.value),
                                                                      (o.color = shadeHexColor(l.bgcolor)),
                                                                      o.setDirtyCanvas(!0, !0));
                                                              }),
                                                              l.setDirtyCanvas(!0, !0));
                                                      },
                                                  }),
                                              ],
                                          ),
                                      ]),
                                  )));
                      } catch (e) {
                          console.debug('[Eclipse.colors] Error adding custom color pickers:', e);
                      }
                      return s;
                  })
                : console.debug('[Eclipse.colors] LGraphCanvas.onMenuNodeColors not available');
        },
    }),
    !LGraphCanvas.prototype.eclipseSetNodeDimension)
) {
    if (((window.eclipse_newNodeMenuAPIUsed = !1), !document.getElementById('eclipse-dialog-style'))) {
        const e = document.createElement('style');
        ((e.id = 'eclipse-dialog-style'),
            (e.innerHTML =
                '\n    .eclipse-dialog {\n      position: fixed;\n      top: 10px;\n      left: 10px;\n      min-height: 1em;\n      background-color: var(--comfy-menu-bg, #222);\n      color: var(--descrip-text, #ddd);\n      font-size: 1.0rem;\n      box-shadow: 0 0 7px black !important;\n      z-index: 10000;\n      display: grid;\n      border-radius: 7px;\n      padding: 7px 7px;\n    }\n    .eclipse-dialog .name { display:inline-block; font-size:14px; padding:0; justify-self:center; }\n    .eclipse-dialog input, .eclipse-dialog textarea, .eclipse-dialog select { margin:3px; min-width:60px; min-height:1.5em; background-color: var(--comfy-input-bg, #333); border:2px solid var(--border-color, #444); color: var(--input-text, #fff); border-radius:14px; padding-left:10px; outline:none; }\n    .eclipse-dialog button { margin-top:3px; vertical-align:top; background-color:#999; border:0; padding:4px 18px; border-radius:20px; cursor:pointer; }\n    '),
            document.head.appendChild(e));
    }
    var _eclipseLastMouse = { x: 0, y: 0 };
    (document.addEventListener(
        'pointerdown',
        function (e) {
            ((_eclipseLastMouse.x = e.clientX), (_eclipseLastMouse.y = e.clientY));
        },
        !0,
    ),
        (LGraphCanvas.prototype.eclipseCreateDialog = function (e, o, t) {
            var n = document.createElement('div');
            ((n.is_modified = !1),
                (n.className = 'eclipse-dialog'),
                (n.innerHTML = e + "<button id='ok'>OK</button>"),
                (n.close = function () {
                    n.parentNode && n.parentNode.removeChild(n);
                }));
            var i = Array.from(n.querySelectorAll('input, select'));
            (i.forEach((e) => {
                e.addEventListener('keydown', function (e) {
                    if (((n.is_modified = !0), 27 == e.keyCode)) (t && t(), n.close());
                    else if (13 == e.keyCode)
                        (o &&
                            o(
                                n,
                                i.map((e) => e.value),
                            ),
                            n.close());
                    else if (13 != e.keyCode && 'textarea' != e.target.localName) return;
                    (e.preventDefault(), e.stopPropagation());
                });
            }),
                _eclipseLastMouse.x || _eclipseLastMouse.y
                    ? ((n.style.left = _eclipseLastMouse.x - 20 + 'px'),
                      (n.style.top = _eclipseLastMouse.y - 20 + 'px'))
                    : ((n.style.left = 0.5 * window.innerWidth - 60 + 'px'),
                      (n.style.top = 0.5 * window.innerHeight - 20 + 'px')),
                n.querySelector('#ok').addEventListener('click', function () {
                    (o &&
                        o(
                            n,
                            i.map((e) => e.value),
                        ),
                        n.close());
                }),
                document.body.appendChild(n),
                i && i[0].focus());
            var l = null;
            return (
                n.addEventListener('mouseleave', function (e) {
                    LiteGraph.dialog_close_on_mouse_leave &&
                        !n.is_modified &&
                        LiteGraph.dialog_close_on_mouse_leave &&
                        (l = setTimeout(n.close, LiteGraph.dialog_close_on_mouse_leave_delay));
                }),
                n.addEventListener('mouseenter', function (e) {
                    LiteGraph.dialog_close_on_mouse_leave && l && clearTimeout(l);
                }),
                n
            );
        }),
        (LGraphCanvas.prototype.eclipseSetNodeDimension = function (e) {
            const o = e.size[0],
                t = e.size[1];
            let n = "<input type='text' class='width' value='" + o + "'></input>";
            ((n += "<input type='text' class='height' value='" + t + "'></input>"),
                LGraphCanvas.prototype.eclipseCreateDialog(
                    "<span class='name'>Width/Height</span>" + n,
                    function (n, i) {
                        var l = Number(i[0]) || o,
                            s = Number(i[1]) || t;
                        let a = e.computeSize();
                        var r = Math.max(a[0], l),
                            c = Math.max(a[1], s);
                        e.setSize([r, c]);
                        var p = document.querySelector('[data-node-id="' + e.id + '"]');
                        if (p) {
                            var d = ('undefined' != typeof LiteGraph && LiteGraph.NODE_TITLE_HEIGHT) || 30;
                            (p.style.setProperty('--node-width', r + 'px'),
                                p.style.setProperty('--node-height', c + d + 'px'));
                        }
                        (n.parentNode && n.parentNode.removeChild(n), e.setDirtyCanvas(!0, !0));
                    },
                    null,
                ));
        }));
    const e = LGraphCanvas.prototype.showContextMenu;
    let o = !1;
    ((LGraphCanvas.prototype.showContextMenu = function (t, n) {
        if (((LGraphCanvas.prototype.showContextMenu = e), !window.eclipse_newNodeMenuAPIUsed && !o)) {
            o = !0;
            const e = LGraphCanvas.prototype.getNodeMenuOptions;
            LGraphCanvas.prototype.getNodeMenuOptions = function (o) {
                const t = e.apply(this, arguments);
                try {
                    const e = {
                            content: 'Eclipse: Node Dimensions',
                            callback: () => {
                                LGraphCanvas.prototype.eclipseSetNodeDimension(o);
                            },
                        },
                        n = {
                            content: 'Eclipse: Reload Node',
                            callback: () => {
                                try {
                                    LGraphCanvas.prototype.eclipseReloadNode(o);
                                } catch (e) {
                                    console.debug('eclipse: Reload Node failed', e);
                                }
                            },
                        },
                        i = t.some((e) => e && e.content && String(e.content).includes('Eclipse: Node Dimensions')),
                        l = t.some((e) => e && e.content && String(e.content).includes('Eclipse: Reload Node'));
                    if (i || l) {
                        if (!i && l) t.splice(t.length - 1, 0, e);
                        else if (i && !l) {
                            const e = t.findIndex(
                                (e) => e && e.content && String(e.content).includes('Node Dimensions'),
                            );
                            e >= 0 ? t.splice(e + 1, 0, n) : t.splice(t.length - 1, 0, n);
                        }
                    } else t.splice(t.length - 1, 0, e, n);
                } catch (e) {
                    console.debug('eclipse: failed to inject Node Dimensions menu item', e);
                }
                return t;
            };
        }
        return e.apply(this, arguments);
    }),
        (LGraphCanvas.prototype.eclipseReloadNode = function (e) {
            try {
                const l = 'converted-widget',
                    s = Symbol();
                function o(e, o) {
                    const { nodeData: t } = o.constructor;
                    return t?.input?.required[e] ?? t?.input?.optional?.[e];
                }
                function t(e, o, n = '') {
                    if (
                        ((o.origType = o.type),
                        (o.origComputeSize = o.computeSize),
                        (o.origSerializeValue = o.serializeValue),
                        (o.computeSize = () => [0, -4]),
                        (o.type = l + n),
                        (o.serializeValue = () => {
                            if (!e.inputs) return;
                            let t = e.inputs.find((e) => e.widget?.name === o.name);
                            return t && t.link ? (o.origSerializeValue ? o.origSerializeValue() : o.value) : void 0;
                        }),
                        o.linkedWidgets)
                    )
                        for (const n of o.linkedWidgets) t(e, n, ':' + o.name);
                }
                function n(e, o, n) {
                    t(e, o);
                    const { type: i } = (function (e) {
                            let o = e[0];
                            return (o instanceof Array && (o = 'COMBO'), { type: o });
                        })(n),
                        l = e.size;
                    e.addInput(o.name, i, { widget: { name: o.name, [s]: () => n } });
                    for (const o of e.widgets) o.last_y += LiteGraph.NODE_SLOT_HEIGHT;
                    (e.setSize([Math.max(l[0], e.size[0]), Math.max(l[1], e.size[1])]), patchNodeCSSSize(e));
                }
                const { title: a, color: r, bgcolor: c } = e.properties.origVals || e,
                    p = { size: [...e.size], color: r, bgcolor: c, pos: [...e.pos] },
                    d = e,
                    u = [],
                    g = [];
                if (e.inputs)
                    for (const h of e.inputs ?? [])
                        if (h.link) {
                            const m = h.name,
                                v = e.findInputSlot(m),
                                b = e.getInputNode(v),
                                _ = e.getInputLink(v);
                            u.push([_.origin_slot, b, m]);
                        }
                if (e.outputs)
                    for (const x of e.outputs)
                        if (x.links) {
                            const C = x.name;
                            for (const E of x.links) {
                                const w = app.graph.links[E],
                                    L = app.graph._nodes_by_id[w.target_id];
                                g.push([C, L, w.target_slot]);
                            }
                        }
                app.graph.remove(e);
                const f = app.graph.add(LiteGraph.createNode(d.constructor.type, a, p));
                f?.constructor?.hasOwnProperty('ttNnodeVersion') &&
                    (f.properties.ttNnodeVersion = f.constructor.ttNnodeVersion);
                let y = d.widgets_values;
                if (y) {
                    let N = !1;
                    const S = y.length <= f.widgets.length;
                    let k = S ? 0 : y.length - 1;
                    const M = (e, o) =>
                        !['', null].includes(e) || ('button' !== o.type && 'converted-widget' !== o.type)
                            ? ('boolean' == typeof e && o.options?.on && o.options?.off) ||
                              o.options?.values?.includes(e)
                                ? { value: e, isValid: !0 }
                                : !o.inputEl || ('string' != typeof e && e !== o.value)
                                  ? !isNaN(e) && ((e = parseFloat(e)), o.options?.min <= e && e <= o.options?.max)
                                      ? { value: e, isValid: !0 }
                                      : { value: o.value, isValid: !1 }
                                  : { value: e, isValid: !0 }
                            : { value: e, isValid: !0 };
                    function i(e) {
                        const o = d.widgets[e];
                        let t = f.widgets[e],
                            n = k;
                        if (
                            t.name === o.name &&
                            (t.type === o.type || 'ttNhidden' === o.type || 'ttNhidden' === t.type)
                        ) {
                            for (; (S ? n < y.length : n >= 0) && !N; ) {
                                let e = M(y[n], t),
                                    o = e.value;
                                if (((N = e.isValid), N && NaN !== o)) {
                                    t.value = o;
                                    break;
                                }
                                n += S ? 1 : -1;
                            }
                            S
                                ? (n === k && k++, n === k + 1 && (k++, k++))
                                : (n === k && k--, n === k - 1 && (k--, k--));
                        }
                    }
                    if (S) for (let z = 0; z < f.widgets.length; z++) i(z);
                    else for (let D = f.widgets.length - 1; D >= 0; D--) i(D);
                } else
                    f.widgets.forEach((e, o) => {
                        let t = !1;
                        for (; o < d.widgets.length && !t; ) {
                            const n = d.widgets[o];
                            (e.type === n.type && ((e.value = n.value), (t = !0)), o++);
                        }
                    });
                (!(function () {
                    for (let e of d.widgets)
                        if (e.type === l) {
                            const t = o(e.name, d),
                                i = f.widgets.find((o) => o.name === e.name);
                            i && !f?.inputs?.find((o) => o.name === e.name) && n(f, i, t);
                        }
                    for (let e of u) {
                        const [o, t, n] = e;
                        t.connect(o, f.id, n);
                    }
                    for (let e of g) {
                        const [o, t, n] = e;
                        f.connect(o, t, n);
                    }
                })(),
                    f.setSize(p.size),
                    patchNodeCSSSize(f),
                    'function' == typeof f.onResize && f.onResize([0, 0]),
                    f.setDirtyCanvas(!0, !0));
            } catch (G) {
                console.debug('eclipse: eclipseReloadNode exception', G);
            }
        }));
}
(app.registerExtension({
    name: 'Eclipse.nodeMenuItems',
    getNodeMenuItems: (e) => (
        (window.eclipse_newNodeMenuAPIUsed = !0),
        [
            {
                content: 'Eclipse: Node Dimensions',
                callback: () => {
                    LGraphCanvas.prototype.eclipseSetNodeDimension(e);
                },
            },
            {
                content: 'Eclipse: Reload Node',
                callback: () => {
                    try {
                        LGraphCanvas.prototype.eclipseReloadNode(e);
                    } catch (e) {
                        console.debug('eclipse: Reload Node failed', e);
                    }
                },
            },
        ]
    ),
}),
    app.registerExtension({
        name: 'Eclipse.appearance',
        nodeCreated(e) {
            try {
                const t = e.title || e.constructor?.title || '',
                    n = e.comfyClass || '',
                    i = e.constructor?.type || '',
                    l = e.type || '',
                    s = (v) => 'string' == typeof v && (v.includes('[Eclipse]') || v.includes('[SmartLML]') || v.includes('[RvTools]')),
                    a = (v) =>
                        'string' == typeof v &&
                        (v.startsWith('Rv') || v.includes('Rv') || v.toLowerCase().includes('rv'));
                // Category-specific title bar colors
                const _catColors = {
                    loader:   '#8131d0', // purple (129,49,208)
                    text:     '#007d52', // teal-green (0,125,82)
                    image:    '#95541e', // warm orange (149,84,30)
                    settings: '#4e4e4e', // standard (default title)
                    pipe:     '#000000', // black (hidden behind setters)
                    router:   '#000000', // black
                    video:    '#2a3c5a', // slate blue (42,60,90)
                    folder:   '#4a2636', // dark rose (74,38,54)
                    tools:    '#4e4e4e', // standard (default title)
                };
                // Category-specific bg colors (only where different from default)
                const _catBgColors = {
                    pipe:     '#000000', // black
                    router:   '#000000', // black
                };
                function _getCat(id) {
                    if (!id || typeof id !== 'string') return 'tools';
                    // Pipe nodes first (Pipe Out variants contain other category keywords)
                    if (/^Pipe |^Pipe IO |^IO |^Context |Concat Pipe|Generation Data|^Pipe In /i.test(id)) return 'pipe';
                    // SmartLML nodes → text (before loader check, since they contain "Loader")
                    if (/Language Model|SmartLML/i.test(id)) return 'text';
                    // Loaders (any node with "Loader" in the name)
                    if (/Loader/i.test(id)) return 'loader';
                    // Router-like tools (black) — before general tools check
                    if (/Repeater|Node Collector|Calculator/i.test(id)) return 'router';
                    // Tools (before text, to catch "Lora Stack to String" etc.)
                    if (/Lora Stack|Block Swap|VRAM|RAM Cleanup|^Fast |Muter|Bypasser|^Stop |Show Any|Nunchaku PuLID/i.test(id)) return 'tools';
                    // Settings (before image, to catch "Image Resolution")
                    if (/Resolution|Sampler|Custom Size|WanVideo Setup|ControlNet|Sampler Selection|Load Directory|Filename Generator|VHS Input|Aspect Ratio/i.test(id)) return 'settings';
                    // Text/Prompt (includes Seed)
                    if (/String|Prompt|Wildcard|Replace String|Multiline|^Seed /i.test(id)) return 'text';
                    // Image
                    if (/Image|Mask|Watermark|Bboxes|Detection|Convert To Batch/i.test(id)) return 'image';
                    // Video
                    if (/Video Clip|Seamless Join/i.test(id)) return 'video';
                    // Router/Logic
                    if (/Passer|Switch|IF A|^Boolean |^Float |^Integer |Multi-Switch/i.test(id)) return 'router';
                    // Folder
                    if (/Folder|Filename Prefix|^Add Folder|^Project Folder/i.test(id)) return 'folder';
                    return 'tools';
                }
                function o() {
                    const cat = _getCat(n);
                    ((e.color = _catColors[cat] || _catColors.tools),
                        (e.bgcolor = _catBgColors[cat] || '#3a3a3a'),
                        (e.shape = 'default'),
                        e.setDirtyCanvas?.(!0, !0),
                        (e._Eclipse_appearance_applied = !0));
                }
                if (s(t) || s(n) || s(e.constructor?.title) || a(n) || a(i) || a(l))
                    if (e._Eclipse_appearance_applied);
                    else {
                        (void 0 === e._Eclipse_initial_bgcolor && (e._Eclipse_initial_bgcolor = e.bgcolor),
                            void 0 === e._Eclipse_initial_color && (e._Eclipse_initial_color = e.color));
                        (e.bgcolor === e._Eclipse_initial_bgcolor && e.color === e._Eclipse_initial_color && o(),
                            setTimeout(() => {
                                if (e._Eclipse_appearance_applied) return;
                                e.bgcolor === e._Eclipse_initial_bgcolor && e.color === e._Eclipse_initial_color && o();
                            }, 50));
                    }
            } catch (r) {}
        },
    }));
