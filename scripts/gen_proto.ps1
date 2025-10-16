param(
  [string]$Proto="ml_grpc/model.proto",
  [string]$OutDir="ml_grpc/generated"
)

python -m grpc_tools.protoc `
  -I. `
  --python_out=$OutDir `
  --grpc_python_out=$OutDir `
  $Proto

Write-Host "Generated stubs in $OutDir"
