pub fn read_nonblocking(fd: i32, buf: &mut Vec<u8>) -> Result<Vec<String>, ()> {
    let mut tmp = [0u8; 65536];
    let n = unsafe { libc::read(fd, tmp.as_mut_ptr() as *mut libc::c_void, tmp.len()) };
    if n < 0 {
        let err = std::io::Error::last_os_error();
        if err.kind() == std::io::ErrorKind::WouldBlock {
            return Ok(Vec::new());
        }
        return Err(());
    }
    if n == 0 {
        return Err(());
    }
    buf.extend_from_slice(&tmp[..n as usize]);
    if buf.len() > 65536 {
        buf.clear();
        return Ok(Vec::new());
    }
    let mut lines = Vec::new();
    while let Some(pos) = buf.iter().position(|&b| b == b'\n') {
        let line: Vec<u8> = buf.drain(..=pos).collect();
        lines.push(String::from_utf8_lossy(&line[..line.len() - 1]).into_owned());
    }
    Ok(lines)
}
