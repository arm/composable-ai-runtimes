-- Disable portal integration in a headless container runtime.
-- WirePlumber's default access rules enable the portal by default,
-- but xdg-desktop-portal is not present in this container.
if default_access == nil or default_access.properties == nil then
  return
end
default_access.properties["enable-flatpak-portal"] = false
