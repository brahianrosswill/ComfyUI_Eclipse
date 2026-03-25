import { app } from './comfy/index.js';
import {
    debounce,
    canvasDirtyBatcher,
    smartResize,
    createWidgetVisibilityManager,
} from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Smart Folder [Eclipse]';
app.registerExtension({
    name: 'Eclipse.SmartFolder',
    async beforeRegisterNodeDef(e, t, i) {
        if (t.name !== NODE_NAME) return;
        const a = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = a ? a.apply(this, arguments) : void 0,
                t = this,
                i = createWidgetVisibilityManager(t);
            ((t._Eclipse_lastBatchNumber = null), (t._Eclipse_lastSkipFirstFramesCalc = null));
            const s = (e, t) => i.setVisible(e, t),
                o = (e) => i.getValue(e),
                c = () => {
                    if (-1 === t.id) return;
                    const e = o('generation_mode'),
                        i = o('create_date_time_folder'),
                        a = o('create_batch_folder'),
                        c = o('use_image_size'),
                        l = 'Image Mode' === e,
                        r = 'Video Mode' === e,
                        n = 'Custom' === o('image_size'),
                        _ = 'Custom' === o('video_size');
                    (s('date_time_format', i),
                        s('date_time_position', i),
                        s('root_folder_image', l),
                        s('use_image_size', l),
                        s('image_size', l && c),
                        s('width', l && c && n),
                        s('height', l && c && n),
                        s('root_folder_video', r),
                        s('video_size', r),
                        s('video_width', r && _),
                        s('video_height', r && _),
                        s('frame_rate', r),
                        s('frame_load_cap', r),
                        s('context_length', r),
                        s('loop_count', r),
                        s('overlap', r),
                        s('skip_first_frames', r),
                        s('skip_calculation', r),
                        s('skip_calculation_control', r),
                        s('select_every_nth', r),
                        s('batch_folder_name', a),
                        s('batch_number', a),
                        s('batch_number_control', a),
                        s('batch_size', l),
                        smartResize(t));
                },
                l = debounce(c, 100);
            ([
                'generation_mode',
                'create_date_time_folder',
                'create_batch_folder',
                'use_image_size',
                'image_size',
                'video_size',
                'root_folder_image',
                'root_folder_video',
            ].forEach((e) => {
                const i = t.widgets?.find((t) => t.name === e);
                if (i) {
                    const e = i.callback;
                    i.callback = function (t) {
                        (l(), e && e(t));
                    };
                }
            }),
                setTimeout(() => {
                    t._Eclipse_initialized || ((t._Eclipse_initialized = !0), c());
                }, 0));
            const r = t.onConfigure;
            return (
                (t.onConfigure = function (e) {
                    (r && r.apply(this, arguments),
                        setTimeout(() => {
                            c();
                        }, 100));
                }),
                e
            );
        };
    },
    async setup() {
        const e = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const t = await e.apply(this, arguments),
                i = app.graph._nodes;
            for (const e of i)
                if (e.type === NODE_NAME) {
                    if (2 === e.mode || 4 === e.mode) continue;
                    const i = String(e.id);
                    if (t.output && t.output[i]) {
                        const a = t.output[i].inputs,
                            s = e.widgets?.find((e) => 'batch_number' === e.name),
                            o = e.widgets?.find((e) => 'batch_number_control' === e.name);
                        if (s && o && a)
                            if ('increment' === o.value)
                                if (null != e._Eclipse_lastBatchNumber) {
                                    const i = e._Eclipse_lastBatchNumber + 1;
                                    try {
                                        const e = a.batch_number;
                                        (a.batch_number && Number(e) === i) || (a.batch_number = i);
                                    } catch (e) {
                                        a.batch_number = i;
                                    }
                                    e._Eclipse_lastBatchNumber = i;
                                    try {
                                        Number(s.value) !== i && (s.value = i);
                                    } catch (e) {}
                                    if (t.workflow && t.workflow.nodes) {
                                        const a = t.workflow.nodes.find((t) => t.id === e.id);
                                        if (a && a.widgets_values) {
                                            const t = e.widgets.indexOf(s);
                                            if (t >= 0)
                                                try {
                                                    a.widgets_values[t] !== i && (a.widgets_values[t] = i);
                                                } catch (e) {}
                                        }
                                    }
                                } else e._Eclipse_lastBatchNumber = s.value;
                            else e._Eclipse_lastBatchNumber = s.value;
                        const c = e.widgets?.find((e) => 'skip_calculation' === e.name),
                            l = e.widgets?.find((e) => 'skip_calculation_control' === e.name);
                        if (c && l && a)
                            if ('increment' === l.value)
                                if (null != e._Eclipse_lastSkipFirstFramesCalc) {
                                    const i = e._Eclipse_lastSkipFirstFramesCalc + 1;
                                    try {
                                        const e = a.skip_calculation;
                                        (a.skip_calculation && Number(e) === i) || (a.skip_calculation = i);
                                    } catch (e) {
                                        a.skip_calculation = i;
                                    }
                                    if (
                                        ((e._Eclipse_lastSkipFirstFramesCalc = i),
                                        Number(c.value) !== i && (c.value = i),
                                        t.workflow && t.workflow.nodes)
                                    ) {
                                        const a = t.workflow.nodes.find((t) => t.id === e.id);
                                        if (a && a.widgets_values) {
                                            const t = e.widgets.indexOf(c);
                                            if (t >= 0)
                                                try {
                                                    a.widgets_values[t] !== i && (a.widgets_values[t] = i);
                                                } catch (e) {}
                                        }
                                    }
                                } else e._Eclipse_lastSkipFirstFramesCalc = c.value;
                            else e._Eclipse_lastSkipFirstFramesCalc = c.value;
                    }
                }
            return t;
        };
    },
});
