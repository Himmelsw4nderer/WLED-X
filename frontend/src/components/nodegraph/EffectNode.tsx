import { memo } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import { useNodeGraphContext } from "./NodeGraphContext";
import { NodePreviewBadge } from "./NodePreviewBadge";
import { ParamControl } from "./ParamControl";
import { categoryColor, SOCKET_COLORS } from "./socketColors";
import "./EffectNode.css";

// The one generic reactflow node renderer for every node type: everything about a
// node's shape (sockets, params, category) comes from the NodeTypeDescriptor looked
// up via NodeGraphContext, not from hand-built per-type components.
function EffectNodeComponent({ id, type, data, selected }: NodeProps<Record<string, unknown>>) {
  const { descriptorsByType, updateParam, isExposed, toggleExposed, nodePreview } = useNodeGraphContext();
  const descriptor = type ? descriptorsByType.get(type) : undefined;
  const preview = nodePreview?.[id];

  if (!descriptor) {
    return (
      <div className="effect-node effect-node--unknown">
        <div className="effect-node__header">{type ?? "Unknown node"}</div>
      </div>
    );
  }

  const inputParamKeys = new Set(descriptor.inputs.map((s) => s.key));
  const standaloneParams = descriptor.params.filter((p) => !inputParamKeys.has(p.key));

  return (
    <div className={`effect-node ${selected ? "effect-node--selected" : ""}`}>
      <div className="effect-node__header" style={{ background: categoryColor(descriptor.category) }}>
        <span className="effect-node__label">{descriptor.label}</span>
        <span className="effect-node__category">{descriptor.category}</span>
      </div>

      <div className="effect-node__body">
        {descriptor.inputs.map((socket) => {
          const param = descriptor.params.find((p) => p.key === socket.key);
          return (
            <div key={socket.key} className="effect-node__row effect-node__row--in">
              <Handle
                type="target"
                position={Position.Left}
                id={socket.key}
                className="effect-node__handle"
                data-socket-type={socket.type}
                style={{ background: SOCKET_COLORS[socket.type] }}
              />
              <span className="effect-node__socket-label" title={socket.type}>
                {socket.label}
              </span>
              {param && (
                <ParamControl
                  param={param}
                  value={data[param.key]}
                  compact
                  exposed={isExposed(id, param.key)}
                  onChange={(value) => updateParam(id, param.key, value)}
                  onToggleExposed={() => toggleExposed(id, param.key, param, data[param.key])}
                />
              )}
            </div>
          );
        })}

        {standaloneParams.map((param) => (
          <div key={param.key} className="effect-node__row effect-node__row--param">
            <span className="effect-node__param-label">{param.key}</span>
            <ParamControl
              param={param}
              value={data[param.key]}
              exposed={isExposed(id, param.key)}
              onChange={(value) => updateParam(id, param.key, value)}
              onToggleExposed={() => toggleExposed(id, param.key, param, data[param.key])}
            />
          </div>
        ))}

        {descriptor.outputs.map((socket) => (
          <div key={socket.key} className="effect-node__row effect-node__row--out">
            {preview && <NodePreviewBadge preview={preview} />}
            <span className="effect-node__socket-label" title={socket.type}>
              {socket.label}
            </span>
            <Handle
              type="source"
              position={Position.Right}
              id={socket.key}
              className="effect-node__handle"
              data-socket-type={socket.type}
              style={{ background: SOCKET_COLORS[socket.type] }}
            />
          </div>
        ))}

        {/* Sink nodes (e.g. LED Color) declare no output socket but still get a
            preview -- otherwise the single most important node to debug would
            never show one. */}
        {descriptor.outputs.length === 0 && preview && (
          <div className="effect-node__row effect-node__row--out">
            <NodePreviewBadge preview={preview} />
          </div>
        )}
      </div>
    </div>
  );
}

export const EffectNode = memo(EffectNodeComponent);
