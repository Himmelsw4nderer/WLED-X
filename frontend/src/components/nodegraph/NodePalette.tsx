import type { DragEvent } from "react";
import type { NodeTypeDescriptor } from "../../types";
import { PALETTE_MIME } from "./graphUtils";
import "./NodePalette.css";

interface NodePaletteProps {
  descriptors: NodeTypeDescriptor[];
}

function groupByCategory(descriptors: NodeTypeDescriptor[]): Map<string, NodeTypeDescriptor[]> {
  const groups = new Map<string, NodeTypeDescriptor[]>();
  for (const d of descriptors) {
    const list = groups.get(d.category);
    if (list) list.push(d);
    else groups.set(d.category, [d]);
  }
  return groups;
}

export function NodePalette({ descriptors }: NodePaletteProps) {
  const groups = groupByCategory(descriptors);

  function handleDragStart(event: DragEvent<HTMLDivElement>, type: string) {
    event.dataTransfer.setData(PALETTE_MIME, type);
    event.dataTransfer.effectAllowed = "move";
  }

  return (
    <aside className="node-palette">
      <div className="node-palette__title">Nodes</div>
      {descriptors.length === 0 && <p className="node-palette__empty">No node types available.</p>}
      {[...groups.entries()].map(([category, items]) => (
        <div key={category} className="node-palette__group">
          <div className="node-palette__group-title">{category}</div>
          {items.map((d) => (
            <div
              key={d.type}
              className="node-palette__item"
              draggable
              onDragStart={(e) => handleDragStart(e, d.type)}
              title={`Drag onto the canvas to add a ${d.label} node`}
            >
              {d.label}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
