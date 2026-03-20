use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    _bindings::stub_info()?.generate()?;
    Ok(())
}
