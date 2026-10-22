
locals {
  catalog_name = "workspace"

  layers = toset([
    "bronze",
    "silver",
    "gold"
  ])
}

resource "databricks_schema" "layers" {
  for_each = local.layers

  catalog_name = local.catalog_name
  name         = each.key
  comment      = "BarrioIQ - Camada ${each.key}"
}

resource "databricks_volume" "raw" {
  name         = "raw"
  catalog_name = local.catalog_name
  schema_name  = databricks_schema.layers["bronze"].name
  volume_type  = "MANAGED"

  comment = "Arquivos brutos do BarrioIQ"
}
