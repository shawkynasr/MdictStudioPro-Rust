use crate::{Error,Result};

fn integer(raw:&str)->Result<String> {
    let (negative,digits)=if let Some(rest)=raw.strip_prefix('-') {(true,rest)}
        else {(false,raw.strip_prefix('+').unwrap_or(raw))};
    if digits.is_empty()||!digits.bytes().all(|c|c.is_ascii_digit()) {return Err(Error::new("malformed_workbook","Invalid integer cell lexeme"));}
    let digits=digits.trim_start_matches('0');
    if digits.is_empty() {Ok("0".into())}else{Ok(format!("{}{digits}",if negative {"-"}else{""}))}
}

fn float_repr(value:f64)->Result<String> {
    if !value.is_finite() {return Err(Error::new("unsupported_cell","Nonfinite numeric cells are unsupported"));}
    let sign=if value.is_sign_negative() {"-"}else{""};
    if value==0.0 {return Ok(format!("{sign}0.0"));}
    // Derive the shortest digits from Rust's round-trip representation, then
    // apply Python's notation threshold and exponent zero-padding explicitly.
    let shortest=value.abs().to_string();
    let (mantissa,extra)=if let Some((m,e))=shortest.split_once('e').or_else(||shortest.split_once('E')) {
        (m,e.parse::<i32>().map_err(|_|Error::new("internal","Invalid float exponent"))?)
    }else{(shortest.as_str(),0)};
    let dot=mantissa.find('.').unwrap_or(mantissa.len()) as i32;
    let all=mantissa.replace('.',"");let leading=all.bytes().take_while(|b|*b==b'0').count();
    let digits=all[leading..].trim_end_matches('0');let exponent=dot-leading as i32-1+extra;
    if digits.is_empty() {return Err(Error::new("internal","Missing nonzero float digits"));}
    if !(-4..16).contains(&exponent) {
        let tail=if digits.len()>1 {format!(".{}",&digits[1..])}else{String::new()};
        return Ok(format!("{sign}{}{tail}e{}{:02}",&digits[..1],if exponent<0 {"-"}else{"+"},exponent.abs()));
    }
    let point=exponent+1;
    let fixed=if point<=0 {format!("0.{}{}","0".repeat((-point) as usize),digits)}
        else if point as usize>=digits.len() {format!("{}{}.0",digits,"0".repeat(point as usize-digits.len()))}
        else {format!("{}.{}",&digits[..point as usize],&digits[point as usize..])};
    Ok(format!("{sign}{fixed}"))
}

/// Header str(value) differs from the legacy body helper for whole floats.
/// Integer XML lexemes are kept exact, including values beyond f64 precision.
pub fn normalize_number(raw:&str,header:bool)->Result<String> {
    let raw=raw.trim_matches(crate::py_space);
    if !raw.contains(['.','e','E']) {return integer(raw);}
    let value=raw.parse::<f64>().map_err(|_|Error::new("malformed_workbook","Invalid floating cell lexeme"))?;
    if !value.is_finite() {return Err(Error::new("unsupported_cell","Nonfinite numeric cells are unsupported"));}
    if !header&&value.fract()==0.0 {
        return Ok(if value==0.0 {"0".into()}else{format!("{value:.0}")});
    }
    float_repr(value)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn headers_bodies_exact_integers_and_scientific_notation_stay_distinct() {
        for (raw,header,expected) in [("1.0",true,"1.0"),("1.0",false,"1"),("-0.0",true,"-0.0"),
            ("-0.0",false,"0"),("1e-5",false,"1e-05"),("1e-4",false,"0.0001"),
            ("1e16",true,"1e+16"),("1e16",false,"10000000000000000"),
            ("9007199254740993",false,"9007199254740993"),("+00012",true,"12"),
            ("1e23",false,"99999999999999991611392")] {
            assert_eq!(normalize_number(raw,header).unwrap(),expected);
        }
    }
}
