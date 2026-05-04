export const CAD_WORKSPACE_TINY_BREAKPOINT_PX = 520;
export const CAD_WORKSPACE_WIDE_BREAKPOINT_PX = 1024;
export const CAD_WORKSPACE_BREAKPOINT_PX = CAD_WORKSPACE_WIDE_BREAKPOINT_PX;

export const CAD_WORKSPACE_DESKTOP_MEDIA_QUERY = `(min-width: ${CAD_WORKSPACE_WIDE_BREAKPOINT_PX}px)`;
export const CAD_WORKSPACE_MOBILE_MEDIA_QUERY = `(max-width: ${CAD_WORKSPACE_WIDE_BREAKPOINT_PX - 1}px)`;

export const CAD_WORKSPACE_LAYOUT_MODE = Object.freeze({
  WIDE: "wide",
  COMPACT: "compact",
  TINY: "tiny"
});

export function getCadWorkspaceLayoutMode(width) {
  const numericWidth = Number(width);
  if (!Number.isFinite(numericWidth)) {
    return CAD_WORKSPACE_LAYOUT_MODE.WIDE;
  }
  if (numericWidth >= CAD_WORKSPACE_WIDE_BREAKPOINT_PX) {
    return CAD_WORKSPACE_LAYOUT_MODE.WIDE;
  }
  if (numericWidth >= CAD_WORKSPACE_TINY_BREAKPOINT_PX) {
    return CAD_WORKSPACE_LAYOUT_MODE.COMPACT;
  }
  return CAD_WORKSPACE_LAYOUT_MODE.TINY;
}

export function isCadWorkspaceDesktopViewport(width) {
  return getCadWorkspaceLayoutMode(width) === CAD_WORKSPACE_LAYOUT_MODE.WIDE;
}
