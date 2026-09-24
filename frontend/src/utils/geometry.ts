export interface Point {
  x: number;
  y: number;
}

/**
 * Thuật toán Ray-casting: Kiểm tra điểm có nằm trong đa giác.
 */
export function isPointInPolygon(point: Point, polygon: Point[]): boolean {
  let { x, y } = point;
  let inside = false;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    let xi = polygon[i].x, yi = polygon[i].y;
    let xj = polygon[j].x, yj = polygon[j].y;

    let intersect = ((yi > y) !== (yj > y)) &&
                    (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

/**
 * Lấy tọa độ gót chân từ Bounding Box (chuẩn hóa 0.0 -> 1.0).
 */
export function getFeetPosition(bbox: number[]): Point | null {
  if (!bbox || bbox.length !== 4) return null;
  const [xMin, yMin, xMax, yMax] = bbox;
  return {
    x: (xMin + xMax) / 2, // Giữa chiều ngang
    y: yMax               // Đáy chiều dọc
  };
}